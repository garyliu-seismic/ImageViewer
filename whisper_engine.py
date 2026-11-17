# -*- coding: utf-8 -*-
"""
whisper_engine.py -- faster-whisper 的共用加载 / 转写封装（桌面实时字幕 + 网页版离线字幕共用）

- 模型放 C:\\models\\faster-whisper\\<size>（CTranslate2 格式：model.bin / config.json /
  tokenizer.json / vocabulary.*），可用环境变量 WHISPER_MODEL_DIR 覆盖根目录、
  WHISPER_MODEL 指定尺寸（默认 small）。
- 设备：默认 auto —— 有 CUDA 用 float16，否则 CPU int8；WHISPER_DEVICE=cpu|cuda 可强制。
- pip 装的 nvidia-cublas/cudnn DLL 不在系统 PATH，这里加载前把它们注册进 DLL 搜索路径。
- 抗幻觉：静音/BGM 段 Whisper 会编造文字，所以调用方必须先用 VAD 切句；这里再设
  condition_on_previous_text=False、no_speech_threshold，并丢弃低置信度结果。
"""
from __future__ import annotations

import glob
import os
import site
import threading

MODEL_ROOT = os.environ.get("WHISPER_MODEL_DIR") or r"C:\models\faster-whisper"
DEFAULT_SIZE = os.environ.get("WHISPER_MODEL") or "small"

_lock = threading.Lock()
_models = {}  # (size, device) -> WhisperModel


def _register_cuda_dlls():
    paths = list(site.getsitepackages())
    try:
        paths.append(site.getusersitepackages())
    except Exception:
        pass
    for sp in paths:
        for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(d)
            except Exception:
                pass
            if d not in os.environ.get("PATH", ""):
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def model_dir(size=None):
    return os.path.join(MODEL_ROOT, size or DEFAULT_SIZE)


def available(size=None):
    d = model_dir(size)
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return os.path.isfile(os.path.join(d, "model.bin")) and os.path.isfile(os.path.join(d, "config.json"))


def _pick_device():
    want = (os.environ.get("WHISPER_DEVICE") or "auto").lower()
    if want in ("cpu", "cuda"):
        return want
    try:
        import ctranslate2
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def get_model(size=None):
    """返回（并缓存）WhisperModel。CUDA 失败自动回退 CPU int8。"""
    size = size or DEFAULT_SIZE
    with _lock:
        _register_cuda_dlls()
        from faster_whisper import WhisperModel
        device = _pick_device()
        key = (size, device)
        if key in _models:
            return _models[key]
        path = model_dir(size)
        try:
            if device == "cuda":
                m = WhisperModel(path, device="cuda", compute_type="float16")
            else:
                m = WhisperModel(path, device="cpu", compute_type="int8", cpu_threads=4)
        except Exception:
            if device != "cuda":
                raise
            device = "cpu"
            key = (size, device)
            m = WhisperModel(path, device="cpu", compute_type="int8", cpu_threads=4)
        _models[key] = m
        return m


def transcribe(samples, language="ja", size=None, initial_prompt=None):
    """samples: float32 单声道 16kHz ndarray。返回 [(start, end, text), ...]（秒）。

    不在这里做 VAD（调用方已切句 / 已用 vad_filter 处理整段音频）。"""
    m = get_model(size)
    segs, _info = m.transcribe(
        samples, language=language, beam_size=1, best_of=1, temperature=0.0,
        condition_on_previous_text=False, no_speech_threshold=0.6,
        log_prob_threshold=-1.0, compression_ratio_threshold=2.4,
        initial_prompt=initial_prompt, without_timestamps=False)
    out = []
    for s in segs:
        t = (s.text or "").strip()
        if t:
            out.append((float(s.start), float(s.end), t))
    return out


def transcribe_file_vtt_segments(audio_path, language="ja", size=None, progress=None):
    """整段离线转写（网页版生成 WebVTT 用）：用 faster-whisper 内置 silero VAD 过滤静音。
    返回 [(start, end, text), ...]。progress(done_sec, total_sec) 可选回调。"""
    import wave
    import numpy as np
    m = get_model(size)
    # 自己读 16kHz 单声道 wav（asr_jobs 用 ffmpeg 抽出来的），不走 faster-whisper 内置的 PyAV 解码
    with wave.open(audio_path, "rb") as wf:
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    segs, info = m.transcribe(
        audio, language=language, beam_size=5, temperature=0.0,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False, no_speech_threshold=0.6,
        log_prob_threshold=-1.0, compression_ratio_threshold=2.4)
    total = float(getattr(info, "duration", 0) or 0)
    out = []
    for s in segs:
        t = (s.text or "").strip()
        if t:
            out.append((float(s.start), float(s.end), t))
        if progress:
            progress(float(s.end), total)
    return out


def speech_chunks(audio):
    """faster-whisper 自带 silero VAD：返回 [{"start","end"}]（单位：样本，16kHz）。"""
    _register_cuda_dlls()
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    return get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=500))


def transcribe_block(audio, language="ja", offset_sec=0.0, size=None):
    """流式用：转写一段 float32 16kHz 音频，时间戳加上 offset_sec。VAD 在内部过滤静音/BGM。"""
    m = get_model(size)
    segs, _info = m.transcribe(
        audio, language=language, beam_size=5, temperature=0.0,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False, no_speech_threshold=0.6,
        log_prob_threshold=-1.0, compression_ratio_threshold=2.4)
    out = []
    for s in segs:
        t = (s.text or "").strip()
        if t:
            out.append((float(s.start) + offset_sec, float(s.end) + offset_sec, t))
    return out


def _ts(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d.%03d" % (h, m, s, ms)


def to_vtt(segments):
    lines = ["WEBVTT", ""]
    for i, (a, b, t) in enumerate(segments, 1):
        lines += [str(i), "%s --> %s" % (_ts(a), _ts(b)), t, ""]
    return "\n".join(lines)
