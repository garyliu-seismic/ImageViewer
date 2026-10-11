# -*- coding: utf-8 -*-
"""视频播放相关的纯逻辑 / 构造参数（无 UI、无 VLC 状态依赖）。

从 image_viewer.py 抽取出来的可单测纯函数。第一阶段先抽这些安全的部分；
VLC 播放器的完整门面（封装播放/缩放/区域放大/鼠标穿透等状态）属于更大的一步，
后续再在保持行为不变的前提下逐步迁移。
"""

import os
import hashlib

from viewer_core import clamp, clamp_rz_center, build_crop_geometry


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


class RegionZoom:
    """视频区域放大（Z 键）的纯状态 + 数学，无 UI / 无 VLC 依赖。

    从 ComicViewer 抽出来，便于单测：开关、放大框中心 (cx, cy)（归一化 0..1）、
    放大框边长占视频比例 scale（越小越放大）。应用到 VLC 的裁剪/缩放在
    ComicViewer._apply_region_zoom 里完成。
    """

    def __init__(self):
        self.enabled = False
        self.cx = 0.5       # 放大框中心 x（归一化 0..1）
        self.cy = 0.5       # 放大框中心 y（归一化 0..1）
        self.scale = 0.5    # 放大框边长占视频比例（越小越放大）

    def reset(self):
        """回到初始状态：居中、边长 50%（开启区域放大时调用）。"""
        self.cx = self.cy = 0.5
        self.scale = 0.5

    def clamp_center(self):
        """把中心钳制在 [scale/2, 1-scale/2] 内，保证放大框不出界。"""
        self.cx, self.cy = clamp_rz_center(self.cx, self.cy, self.scale)

    def pan(self, dx, dy):
        self.cx += dx
        self.cy += dy
        self.clamp_center()

    def zoom_step(self, d):
        """调整放大框边长比例；d<0 放大（框更小），d>0 缩小。"""
        self.scale = clamp(round(self.scale + d, 2), 0.1, 1.0)
        self.clamp_center()

    def reset_center(self):
        self.cx = self.cy = 0.5
        self.clamp_center()

    def crop_geometry(self, w, h):
        """生成 VLC 裁剪字符串（含钳制中心）。"""
        self.clamp_center()
        return build_crop_geometry(w, h, self.cx, self.cy, self.scale)
