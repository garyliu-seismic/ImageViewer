# -*- coding: utf-8 -*-
"""
asr_jobs.py -- 网页版「AI 字幕」后台任务：ffmpeg 流式抽音频 -> VAD 切句 -> faster-whisper -> WebVTT

边读边识别：ffmpeg 把 16kHz 单声道 PCM 写到管道，这里攒够一块（首块约 12 秒，之后约 30 秒）
就在最后一个静音处切开识别，已识别的字幕立刻可取（前端轮询时拿「部分 VTT」），读完后
写入磁盘缓存。云端大文件要把整个文件读一遍（音视频交织），慢在读文件上，但字幕不用干等到最后。

一个视频 + 语言对应一个任务；同一时刻只跑一个转写。网盘/中继卡死（长时间没有新数据）时
杀掉 ffmpeg，从已读到的位置用 -ss 续读重试一次。
"""
from __future__ import annotations

import hashlib
import os
import threading
import time

import ffmpeg_tools

LANGS = {"ja", "en", "zh", "ko"}
SR = 16000
FIRST_BLOCK_SEC = 12          # 第一块攒这么久就识别，让第一句字幕尽早出现
BLOCK_SEC = 30                # 之后每攒这么多秒识别一块
MAX_BLOCK_SEC = 60            # 找不到静音切点时，最多攒到这么久才硬切
RETRY_FLUSH_SEC = 5           # 某次没找到切点后，再多攒这么久才重新尝试（VAD 不是免费的）
TAIL_GUARD_SEC = 1.0         # 只在「离块尾至少这么远」的静音处切，避免切断一句话
STALL_SEC = 90                # 这么久没读到任何新数据 -> 认为卡死
MAX_ATTEMPTS = 2

_lock = threading.Lock()
_jobs = {}              # ck -> {"state","pct","stage","count","segs","error","t0"}
_run_sem = threading.Semaphore(1)


def _ck(key, lang):
    return hashlib.sha1(("%s|%s" % (key, lang)).encode("utf-8")).hexdigest()[:24]


def cache_path(cache_dir, key, lang):
    return os.path.join(cache_dir, _ck(key, lang) + "." + lang + ".vtt")


def status(cache_dir, key, lang):
    with _lock:
        j = _jobs.get(_ck(key, lang))
        if j and j["state"] in ("queued", "running", "error"):
            return {k: v for k, v in j.items() if k != "segs"}
    if os.path.isfile(cache_path(cache_dir, key, lang)):
        return {"state": "done", "pct": 100}
    return {"state": "none", "pct": 0}


def read_vtt(cache_dir, key, lang):
    """已完成 -> 磁盘缓存；还在跑 -> 目前为止的部分字幕；都没有 -> None。"""
    import whisper_engine
    with _lock:
        j = _jobs.get(_ck(key, lang))
        if j and j.get("segs"):
            return whisper_engine.to_vtt(list(j["segs"]))
    p = cache_path(cache_dir, key, lang)
    if not os.path.isfile(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def _probe_duration(ff_input):
    try:
        j = ffmpeg_tools.run_probe(ff_input)
        return float((j.get("format") or {}).get("duration") or 0)
    except Exception:
        return 0.0


def _set(ck, **kw):
    with _lock:
        _jobs.setdefault(ck, {}).update(kw)


def _push_segs(ck, new):
    if not new:
        return
    with _lock:
        j = _jobs.setdefault(ck, {})
        j.setdefault("segs", []).extend(new)
        j["count"] = len(j["segs"])


def start(cache_dir, key, lang, make_src, size=None):
    """启动（或复用）任务。make_src() -> 一个有 .ff_input / .close() 的源（任务线程里创建，
    保证 nonce 在整个任务期间有效）。返回当前 status。"""
    import whisper_engine
    if lang not in LANGS:
        raise ValueError("不支持的语言")
    if not whisper_engine.available(size):
        raise RuntimeError("没找到 faster-whisper 模型（放到 %s）" % whisper_engine.model_dir(size))
    ck = _ck(key, lang)
    with _lock:
        j = _jobs.get(ck)
        if j and j["state"] in ("queued", "running"):
            return {k: v for k, v in j.items() if k != "segs"}
        if os.path.isfile(cache_path(cache_dir, key, lang)):
            return {"state": "done", "pct": 100}
        _jobs[ck] = {"state": "queued", "pct": 0, "t0": time.time(), "count": 0}
    os.makedirs(cache_dir, exist_ok=True)
    threading.Thread(target=_run, args=(cache_dir, key, lang, make_src, size, ck),
                     daemon=True, name="iv-asr").start()
    return {"state": "queued", "pct": 0}


def _pick_cut(buf, final):
    """返回本块要识别的样本数。非最后一块：在最后一个「离块尾 >= TAIL_GUARD_SEC」的语音段
    结束处切；找不到就整块识别（整块都是静音/连续语音）。"""
    import whisper_engine
    n = len(buf)
    if final:
        return n
    try:
        chunks = whisper_engine.speech_chunks(buf)
    except Exception:
        return n
    # 只在「后面静音 >= TAIL_GUARD_SEC」的语音段末尾切：句子内部的短停顿也会被 VAD 断开，
    # 在那里切会把一句话劈成两半。最后一段的后续静音按「到块尾」算。
    guard = int(TAIL_GUARD_SEC * SR)
    ends = []
    for i, c in enumerate(chunks):
        nxt = chunks[i + 1]["start"] if i + 1 < len(chunks) else n
        if nxt - c["end"] >= guard:
            ends.append(c["end"])
    if ends:
        return max(ends)
    # 没有合适的切点：继续攒，直到 MAX_BLOCK_SEC 才硬切
    return n if n >= MAX_BLOCK_SEC * SR else 0


def _stream(ck, ff_input, lang, size, duration):
    import numpy as np
    import whisper_engine

    ffmpeg = ffmpeg_tools.find_tool("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("没找到 ffmpeg")

    buf = np.zeros(0, dtype=np.float32)
    base = 0            # buf 第一个样本在整条音轨里的绝对下标
    read_total = 0      # 已从管道读到的绝对样本数
    carry = b""
    flushed = False
    next_at = 0          # buf 长度达到这么多样本才尝试切块

    def flush(final):
        nonlocal buf, base, flushed, next_at
        cut = _pick_cut(buf, final)
        if cut <= 0:
            next_at = len(buf) + RETRY_FLUSH_SEC * SR
            return
        next_at = 0
        segs = whisper_engine.transcribe_block(buf[:cut], language=lang, offset_sec=base / SR, size=size)
        _push_segs(ck, segs)
        buf = buf[cut:]
        base += cut
        flushed = True

    for attempt in range(MAX_ATTEMPTS):
        start_sec = read_total / SR
        argv = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin"] + ffmpeg_tools.input_args(ff_input)
        if start_sec > 0:
            argv += ["-ss", "%.3f" % start_sec]
        argv += ["-i", ff_input, "-map", "0:a:0", "-vn", "-sn", "-dn", "-ac", "1", "-ar", str(SR),
                 "-f", "s16le", "pipe:1"]
        p = ffmpeg_tools.popen(argv)
        state = {"last": time.time(), "stalled": False, "done": False}

        def watchdog():
            while not state["done"]:
                time.sleep(1)
                if time.time() - state["last"] > STALL_SEC:
                    state["stalled"] = True
                    ffmpeg_tools.kill(p)
                    return
        threading.Thread(target=watchdog, daemon=True, name="iv-asr-wd").start()
        carry = b""
        try:
            while True:
                data = p.stdout.read(1 << 16)
                if not data:
                    break
                state["last"] = time.time()
                data = carry + data
                usable = len(data) - (len(data) % 2)
                carry = data[usable:]
                if not usable:
                    continue
                pcm = np.frombuffer(data[:usable], dtype=np.int16).astype(np.float32) / 32768.0
                buf = np.concatenate([buf, pcm]) if len(buf) else pcm
                read_total += len(pcm)
                if duration > 0:
                    _set(ck, pct=min(99, int(read_total / SR * 100 / duration)))
                if len(buf) >= max(next_at, int((BLOCK_SEC if flushed else FIRST_BLOCK_SEC) * SR)):
                    flush(False)
            p.wait()
        finally:
            state["done"] = True
            rc = p.returncode
            err = ffmpeg_tools.err_tail(p)
            ffmpeg_tools.kill(p)
        if state["stalled"]:
            if attempt == MAX_ATTEMPTS - 1:
                raise TimeoutError("读取音频卡住了（%d 秒没有新数据，网盘或中继无响应）" % STALL_SEC)
            continue                       # 从已读到的位置续读
        if rc not in (0, None):
            raise RuntimeError("ffmpeg 抽音频失败：%s" % err)
        break
    flush(True)


def _run(cache_dir, key, lang, make_src, size, ck):
    import whisper_engine
    with _run_sem:
        _set(ck, state="running", pct=0, stage="stream")
        src = None
        try:
            src = make_src()
            duration = _probe_duration(src.ff_input)
            _stream(ck, src.ff_input, lang, size, duration)
            with _lock:
                segs = list((_jobs.get(ck) or {}).get("segs") or [])
            vtt = whisper_engine.to_vtt(segs)
            tmp = cache_path(cache_dir, key, lang) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(vtt)
            os.replace(tmp, cache_path(cache_dir, key, lang))
            with _lock:
                _jobs.pop(ck, None)
        except Exception as e:
            _set(ck, state="error", error=str(e)[:300])
        finally:
            if src is not None:
                src.close()
