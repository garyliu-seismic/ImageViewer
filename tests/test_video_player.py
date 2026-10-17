# -*- coding: utf-8 -*-
"""video_player 纯逻辑单元测试。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import video_player as vp


class TestFmtTime(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(vp.fmt_time(0), "0:00")

    def test_seconds(self):
        self.assertEqual(vp.fmt_time(5000), "0:05")

    def test_minutes(self):
        self.assertEqual(vp.fmt_time(61000), "1:01")
        self.assertEqual(vp.fmt_time(60000), "1:00")

    def test_negative_clamped(self):
        self.assertEqual(vp.fmt_time(-999), "0:00")


class TestBuildVlcArgs(unittest.TestCase):
    def test_base(self):
        args = vp.build_vlc_args(0)
        self.assertEqual(args, ["--avcodec-hw=none", "--vout=wingdi",
                                "--no-mouse-events", "--no-keyboard-events", "--quiet"])

    def test_with_rotation(self):
        args = vp.build_vlc_args(90)
        self.assertEqual(args[-2:], ["--video-filter=transform", "--transform-type=90"])
        self.assertEqual(args[0], "--avcodec-hw=none")


class TestBuildVideoMediaOptions(unittest.TestCase):
    def test_no_subtitle(self):
        opts = vp.build_video_media_options(1.0, None)
        self.assertEqual(opts, [":avcodec-hw=none", ":rate=1.000", ":audio-time-stretch"])

    def test_with_subtitle(self):
        opts = vp.build_video_media_options(1.5, r"C:\sub\a.srt")
        self.assertEqual(opts[-1], ":sub-file=C:/sub/a.srt")

    def test_rate_format(self):
        opts = vp.build_video_media_options(2.0, None)
        self.assertEqual(opts[1], ":rate=2.000")


class TestVideoTmpName(unittest.TestCase):
    def test_name_and_ext(self):
        name = vp.video_tmp_name("ch1/vid.mp4", r"C:\tmp")
        self.assertTrue(name.startswith(r"C:\tmp" + os.sep + "v_"))
        self.assertTrue(name.endswith(".mp4"))

    def test_deterministic(self):
        a = vp.video_tmp_name("ch1/vid.mp4", r"C:\tmp")
        b = vp.video_tmp_name("ch1/vid.mp4", r"C:\tmp")
        self.assertEqual(a, b)

    def test_different_entries(self):
        a = vp.video_tmp_name("a.mp4", r"C:\tmp")
        b = vp.video_tmp_name("b.mp4", r"C:\tmp")
        self.assertNotEqual(a, b)


class TestVideoResumeKey(unittest.TestCase):
    def test_tuple_returns_none(self):
        self.assertIsNone(vp.video_resume_key(("a.zip", "v.mp4")))

    def test_path_normalized(self):
        key = vp.video_resume_key("C:/Videos/x.mp4")
        self.assertEqual(key, os.path.normcase(os.path.abspath("C:/Videos/x.mp4")))


class TestRegionZoom(unittest.TestCase):
    def test_initial_state(self):
        rz = vp.RegionZoom()
        self.assertFalse(rz.enabled)
        self.assertEqual((rz.cx, rz.cy, rz.scale), (0.5, 0.5, 0.5))

    def test_reset(self):
        rz = vp.RegionZoom()
        rz.cx, rz.cy, rz.scale = 0.1, 0.9, 0.2
        rz.reset()
        self.assertEqual((rz.cx, rz.cy, rz.scale), (0.5, 0.5, 0.5))

    def test_pan_clamps_to_bounds(self):
        rz = vp.RegionZoom()  # scale=0.5 => 中心范围 [0.25, 0.75]
        rz.pan(10, -10)
        self.assertEqual((rz.cx, rz.cy), (0.75, 0.25))

    def test_zoom_step_clamps_scale(self):
        rz = vp.RegionZoom()
        for _ in range(20):
            rz.zoom_step(-0.1)   # 一直放大
        self.assertAlmostEqual(rz.scale, 0.1)
        for _ in range(20):
            rz.zoom_step(0.1)    # 一直缩小
        self.assertAlmostEqual(rz.scale, 1.0)

    def test_crop_geometry_center(self):
        rz = vp.RegionZoom()
        self.assertEqual(rz.crop_geometry(320, 180), "240x135+80+45")

    def test_crop_geometry_after_pan(self):
        rz = vp.RegionZoom()
        rz.pan(-1, -1)   # 钳到左上角 (0.25, 0.25)
        self.assertEqual(rz.crop_geometry(320, 180), "160x90+0+0")


if __name__ == "__main__":
    unittest.main()
