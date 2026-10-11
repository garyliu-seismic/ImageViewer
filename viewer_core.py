# -*- coding: utf-8 -*-
"""图片 / 漫画浏览器的纯逻辑（无 UI / 无 VLC 依赖）。

从 image_viewer.py 抽取出来的、可独立单测的纯函数：
缩放 / 适配 / 平移钳制 / 区域放大裁剪 / 缩放滑块对数映射 / 自然排序等。

约定：这里的函数不做任何状态修改，输入输出全部通过参数传递，
方便用 unittest 固化当前行为（characterization test），重构时防回归。
"""

import math
import re

# 缩放范围（图片页）：2% ~ 4000%
MIN_ZOOM, MAX_ZOOM = 0.02, 40.0
# 平移时至少保留的可见像素
MIN_VISIBLE = 60


def natural_key(s):
    """自然排序：让 page2 排在 page10 之前。"""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def clamp(v, a, b):
    return min(max(v, a), b)


def rotated_size(w, h, rotation):
    """旋转后的显示尺寸。rotation 为 90/270 时宽高互换。"""
    if rotation % 180 == 90:
        return h, w
    return w, h


def compute_zoom(fit_mode, zoom, cw, ch, rw, rh):
    """按 fit 模式计算缩放倍率（与 ComicViewer._compute_zoom 的数学一致）。

    fit_mode: "width" | "height" | "window" | "actual" | "custom"
    zoom:     自定义模式下的倍率
    cw, ch:   画布可视区宽高
    rw, rh:   旋转后的图片尺寸
    """
    cw = max(cw, 1)
    ch = max(ch, 1)
    if fit_mode == "width":
        z = cw / rw
    elif fit_mode == "height":
        z = ch / rh
    elif fit_mode == "window":
        z = min(cw / rw, ch / rh)
    elif fit_mode == "actual":
        z = 1.0
    else:  # custom
        z = zoom
    return clamp(z, MIN_ZOOM, MAX_ZOOM)


def clamp_pan(pan_x, pan_y, cw, ch, rw, rh, zoom):
    """把平移量钳制到合理范围（图片边缘至少露出 MIN_VISIBLE 像素）。"""
    cw = max(cw, 1)
    ch = max(ch, 1)
    rw, rh = rw * zoom, rh * zoom
    maxx = 0 if rw <= cw else (rw - cw) / 2 + MIN_VISIBLE
    maxy = 0 if rh <= ch else (rh - ch) / 2 + MIN_VISIBLE
    return clamp(pan_x, -maxx, maxx), clamp(pan_y, -maxy, maxy)


def zoom_at_pan(pan_x, pan_y, x, y, cw, ch, f):
    """以画布上某点 (x, y) 为锚点缩放时的平移调整（f = new_zoom / old_zoom）。"""
    return pan_x * f + (x - cw / 2) * (1 - f), pan_y * f + (y - ch / 2) * (1 - f)


def clamp_rz_center(cx, cy, scale):
    """区域放大：把放大框中心钳制在 [scale/2, 1-scale/2] 内，保证框不出界。"""
    lo = scale / 2.0
    hi = 1.0 - lo
    return clamp(cx, lo, hi), clamp(cy, lo, hi)


def build_crop_geometry(w, h, cx, cy, scale):
    """生成 VLC 区域放大裁剪字符串。

    注意 VLC 实测格式："WxH+X+Y" 中 W=右边界、H=下边界、X=左边界、Y=上边界，
    即裁剪矩形 = [X, W] × [Y, H]。这里返回「右下角 x 右下角 + 左上角 + 左上角」。
    """
    box_w = max(1, int(round(w * scale)))
    box_h = max(1, int(round(h * scale)))
    x = int(round(cx * w - box_w / 2.0))
    y = int(round(cy * h - box_h / 2.0))
    return "%dx%d+%d+%d" % (x + box_w, y + box_h, x, y)


def zoom_slider_value(pos, lo, hi):
    """缩放滑块 0..1000 -> 真实倍率（对数刻度，拖动手感均匀）。"""
    return lo * (hi / lo) ** (float(pos) / 1000.0)


def zoom_slider_pos(z, lo, hi):
    """真实倍率 -> 缩放滑块 0..1000（对数刻度）。"""
    z = clamp(z, lo, hi)
    return int(round(1000.0 * math.log(z / lo) / math.log(hi / lo)))
