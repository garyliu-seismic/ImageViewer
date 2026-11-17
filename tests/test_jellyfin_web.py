# -*- coding: utf-8 -*-
"""网页版 Jellyfin：假 Jellyfin 服务器 + 真后端，端到端走 登录 / 浏览 / Range 播放 / 海报墙 peek / 字幕 / 海报。"""
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import web_backend as wb
from tests.test_media_endpoints import req, jbody

VIDEO = bytes(range(256)) * 40          # 10240 字节，方便验 Range
UID = "u" * 32
LIB, SHOW, SEASON, EP1, EP2, MOVIE = ("lib00000", "show0000", "season00", "ep000001", "ep000002", "movie000")


def item(i, name, typ, folder=False, **kw):
    d = {"Id": i, "Name": name, "Type": typ, "IsFolder": folder, "ImageTags": {"Primary": "tag1"}}
    d.update(kw)
    return d


TREE = {
    "": [item(LIB, "电影与剧集", "CollectionFolder", True)],
    LIB: [item(SHOW, "示例剧", "Series", True, ProductionYear=2020), item(MOVIE, "示例电影", "Movie", ProductionYear=2019,
          Overview="电影简介", CommunityRating=7.8, OriginalTitle="Sample Movie", RunTimeTicks=72000000000,
          Genres=["剧情"], Container="mp4", MediaSources=[{"Id": MOVIE, "Container": "mp4", "Size": 10240}],
          MediaStreams=[{"Type": "Subtitle", "Index": 2, "Language": "chi", "DisplayTitle": "简体中文 (SRT)"}])],
    SHOW: [item(SEASON, "第 1 季", "Season", True)],
    SEASON: [item(EP1, "第一集", "Episode", SeriesId=SHOW, SeriesName="示例剧", ParentIndexNumber=1, IndexNumber=1,
                  Container="mkv", MediaSources=[{"Id": EP1, "Container": "mkv", "Size": 10240}], MediaStreams=[]),
             item(EP2, "第二集", "Episode", SeriesId=SHOW, SeriesName="示例剧", ParentIndexNumber=1, IndexNumber=2,
                  Container="mkv", MediaSources=[{"Id": EP2, "Container": "mkv", "Size": 10240}], MediaStreams=[])],
}


class FakeJf(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path.startswith("/Users/AuthenticateByName"):
            if body.get("Username") == "gary" and body.get("Pw") == "pw":
                return self._json({"AccessToken": "TOKEN123", "User": {"Id": UID}})
            return self._json({"error": "bad"}, 401)
        self._json({}, 404)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        FakeJf.seen.append((u.path, self.headers.get("Authorization", "")))
        if "TOKEN123" not in self.headers.get("Authorization", "") and "TOKEN123" not in (q.get("ApiKey") or [""])[0]:
            return self._json({"error": "unauth"}, 401)
        if u.path == "/Users/%s/Items" % UID:
            return self._json({"Items": TREE.get((q.get("ParentId") or [""])[0], [])})
        for parent, items in TREE.items():
            for it in items:
                if u.path == "/Users/%s/Items/%s" % (UID, it["Id"]):
                    return self._json(it)
        if u.path.startswith("/Videos/") and u.path.endswith("/stream"):
            rng = self.headers.get("Range")
            data, code = VIDEO, 200
            if rng and rng.startswith("bytes="):
                a, _, b = rng[6:].partition("-")
                a = int(a); b = int(b) if b else len(VIDEO) - 1
                data, code = VIDEO[a:b + 1], 206
            self.send_response(code)
            self.send_header("Content-Type", "video/x-matroska")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            if code == 206:
                self.send_header("Content-Range", "bytes %d-%d/%d" % (a, a + len(data) - 1, len(VIDEO)))
            self.end_headers()
            self.wfile.write(data)
            return
        if "/Subtitles/2/Stream.vtt" in u.path:
            b = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n你好\n".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/vtt")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
            return
        if "/Images/Primary" in u.path:
            b = b"\x89PNG\r\n\x1a\nFAKE"
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
            return
        self._json({}, 404)


class TestJellyfinWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="iv_jf_")
        cls._old_cfg = wb.CONFIG_PATH
        wb.CONFIG_PATH = os.path.join(cls.tmp, "image_viewer.json")
        wb._remote_cache.clear()
        wb._jf_meta.clear()
        cls.jf = ThreadingHTTPServer(("127.0.0.1", 0), FakeJf)
        threading.Thread(target=cls.jf.serve_forever, daemon=True).start()
        cls.jf_url = "http://127.0.0.1:%d" % cls.jf.server_address[1]
        cls.httpd, _t, url = wb.serve(0, open_browser=False)
        cls.base = url.rstrip("/")
        cls.token = wb.Handler.token

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()
        cls.jf.shutdown(); cls.jf.server_close()
        wb.CONFIG_PATH = cls._old_cfg
        wb._remote_cache.clear()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, route, params=None, **kw):
        return req(self.base, self.token, route, params, **kw)

    def post(self, route, body, **kw):
        return req(self.base, self.token, route, None, "POST", body, **kw)

    def test_00_not_connected(self):
        st, _, b = self.get("/api/jellyfin/config")
        self.assertEqual((st, jbody(b)["connected"]), (200, False))
        st, _, b = self.get("/api/remote/ls", {"path": "/jf"})
        self.assertNotEqual(st, 200)

    def test_01_bad_login_not_saved(self):
        st, _, b = self.post("/api/jellyfin/config", {"base_url": self.jf_url, "username": "gary", "password": "nope"})
        self.assertNotEqual(st, 200)
        self.assertFalse(jbody(self.get("/api/jellyfin/config")[2])["connected"])

    def test_02_full_flow(self):
        st, _, b = self.post("/api/jellyfin/config", {"base_url": self.jf_url, "username": "gary", "password": "pw"})
        self.assertEqual(st, 200, b)
        saved = open(wb.CONFIG_PATH, encoding="utf-8").read()
        self.assertIn("TOKEN123", saved)
        self.assertNotIn('"pw"', saved)                                  # 密码不落盘
        self.assertTrue(jbody(self.get("/api/jellyfin/config")[2])["connected"])

        # 浏览：根 -> 媒体库 -> 剧 -> 季
        j = jbody(self.get("/api/remote/ls", {"path": "/jf"})[2])
        self.assertEqual([e["name"] for e in j["entries"]], ["电影与剧集"])
        self.assertEqual(j["parent"], "")
        lib = j["entries"][0]["path"]
        self.assertEqual(lib, "/jf/" + LIB)
        j = jbody(self.get("/api/remote/ls", {"path": lib})[2])
        self.assertEqual(j["parent"], "/jf")
        kinds = {e["name"]: e for e in j["entries"]}
        self.assertEqual(kinds["示例剧"]["kind"], "dir")
        movie = kinds["示例电影.mp4"]
        self.assertEqual((movie["kind"], movie["path"]), ("video", "/jf/%s/%s.mp4" % (LIB, MOVIE)))
        self.assertEqual(movie["subs"][0]["index"], 2)
        j = jbody(self.get("/api/remote/ls", {"path": "/jf/%s/%s/%s" % (LIB, SHOW, SEASON)})[2])
        self.assertEqual(j["parent"], "/jf/%s/%s" % (LIB, SHOW))
        eps = [e for e in j["entries"] if e["kind"] == "video"]
        self.assertEqual(len(eps), 2)
        ep1 = eps[0]["path"]
        self.assertTrue(ep1.endswith(EP1 + ".mkv"))

        # 播放：整段 + Range 都按原样转发（<video> 不需要认证头）
        st, _, b = self.get("/api/remote/data", {"path": ep1})
        self.assertEqual((st, b), (200, VIDEO))
        st, h, b = self.get("/api/remote/data", {"path": ep1}, headers={"Range": "bytes=10-19"})
        self.assertEqual((st, b), (206, VIDEO[10:20]))
        # 凭据只在后端 -> Jellyfin 这一段，浏览器侧响应里不会出现 token
        self.assertNotIn("TOKEN123", json.dumps(dict(h)))

        # 续播 key 不含账号 / token
        self.assertTrue(wb.remote_resume_key(ep1).startswith("jf:127.0.0.1:"))
        self.assertNotIn("TOKEN", wb.remote_resume_key(ep1))

        # 海报墙：用 Jellyfin 自己的元数据，不要 TMDB 令牌
        st, _, b = self.post("/api/scrape/peek", {"items": [{"remote": ep1}, {"remote": eps[1]["path"]}, {"remote": movie["path"]}]})
        pj = jbody(b)
        self.assertEqual(st, 200)
        self.assertTrue(pj["token_configured"])
        a, a2, m = pj["items"]
        self.assertEqual((a["parsed"]["kind"], a["parsed"]["season"], a["parsed"]["episode"]), ("episode", 1, 1))
        self.assertEqual(a["group_key"], a2["group_key"])                # 同一部剧合成一张卡
        self.assertEqual(a["item"]["media"]["title"], "示例剧")
        self.assertEqual(a["item"]["media"]["poster_path"], "jf:" + SHOW)
        self.assertEqual((m["parsed"]["kind"], m["item"]["media"]["poster_path"]), ("movie", "jf:" + MOVIE))
        self.assertEqual(m["item"]["media"]["vote_average"], 7.8)

        # 详情面板：简介来自 Jellyfin
        st, _, b = self.get("/api/scrape/item", {"remote": movie["path"]})
        self.assertEqual(jbody(b)["item"]["media"]["overview_zh"], "电影简介")

        # 海报 / 字幕
        st, h, b = self.get("/api/scrape/image", {"p": "jf:" + MOVIE, "size": "w342"})
        self.assertEqual((st, b[:4]), (200, b"\x89PNG"))
        st, h, b = self.get("/api/remote/jfsub", {"path": movie["path"], "index": 2})
        self.assertEqual(st, 200)
        self.assertIn("你好", b.decode("utf-8"))

        # 非法路径 / 序号
        self.assertNotEqual(self.get("/api/remote/ls", {"path": "/jf/../etc"})[0], 200)
        self.assertNotEqual(self.get("/api/remote/jfsub", {"path": movie["path"], "index": 999})[0], 200)
        self.assertNotEqual(self.get("/api/remote/jfsub", {"path": "/dav/x.mkv", "index": 2})[0], 200)

        # 断开
        self.assertEqual(self.post("/api/jellyfin/disconnect", {})[0], 200)
        self.assertFalse(jbody(self.get("/api/jellyfin/config")[2])["connected"])
        self.assertNotIn("TOKEN123", open(wb.CONFIG_PATH, encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
