# -*- coding: utf-8 -*-
"""视频播放相关的纯逻辑 / 构造参数（无 UI、无 VLC 状态依赖）。

从 image_viewer.py 抽取出来的可单测纯函数。第一阶段先抽这些安全的部分；
VLC 播放器的完整门面（封装播放/缩放/区域放大/鼠标穿透等状态）属于更大的一步，
后续再在保持行为不变的前提下逐步迁移。
"""

import os
import hashlib


def fmt_time(ms):
    """毫秒 -> "m:ss" 显示文本。"""
    if ms < 0:
        ms = 0
    s = ms // 1000
    return "%d:%02d" % (s // 60, s % 60)


def build_vlc_args(rotation):
    """构造 VLC Instance 参数列表。

    关硬件加速 + wingdi 软渲染 + 不接管鼠标/键盘；有旋转时加 transform 滤镜。
    （这些是本机实测稳定运行的组合，不要随意改动）
    """
    args = [
        "--avcodec-hw=none", "--vout=wingdi",
        "--no-mouse-events", "--no-keyboard-events",
    ]
    if rotation:
        args.append("--video-filter=transform")
        args.append("--transform-type=%d" % rotation)
    return args


def build_video_media_options(rate, sub_path):
    """构造 media 级选项列表（关 D3D11VA、速率、可选外挂字幕）。"""
    opts = [":avcodec-hw=none", ":rate=%.3f" % rate, ":audio-time-stretch"]
    if sub_path:
        opts.append(":sub-file=" + sub_path.replace("\\", "/"))
    return opts


def video_tmp_name(entry, tmp_dir):
    """zip 内视频条目 -> 解压后的临时文件名（md5 前 12 位 + 原扩展名）。"""
    name = entry.replace("\\", "/").split("/")[-1]
    ext = os.path.splitext(name)[1].lower()
    return os.path.join(tmp_dir, "v_" + hashlib.md5(entry.encode("utf-8")).hexdigest()[:12] + ext)


def video_resume_key(src):
    """视频续播点的 key：本地文件返回规范化绝对路径，zip 内条目返回 None。"""
    if isinstance(src, tuple):
        return None
    return os.path.normcase(os.path.abspath(src))
