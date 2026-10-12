# -*- coding: utf-8 -*-
"""viewer_core 纯逻辑单元测试（characterization test：固化当前行为）。

只用标准库 unittest，无需联网安装依赖。
运行：  python -m unittest tests.test_core -v   （在项目根目录）
或：    python tests/test_core.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import viewer_core as core


class TestClampAndSort(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(core.clamp(5, 0, 10), 5)
        self.assertEqual(core.clamp(-1, 0, 10), 0)
        self.assertEqual(core.clamp(99, 0, 10), 10)

    def test_natural_key(self):
        self.assertEqual(core.natural_key("page2"), ["page", 2, ""])
        # 自然排序：page2 在 page10 之前
        files = ["page10.jpg", "page2.jpg", "page1.jpg"]
        files.sort(key=core.natural_key)
        self.assertEqual(files, ["page1.jpg", "page2.jpg", "page10.jpg"])

    def test_natural_key_case_insensitive(self):
        self.assertEqual(core.natural_key("ABC"), ["abc"])


class TestRotatedSize(unittest.TestCase):
    def test_no_rotation(self):
        self.assertEqual(core.rotated_size(100, 200, 0), (100, 200))

    def test_90_degrees_swaps(self):
        self.assertEqual(core.rotated_size(100, 200, 90), (200, 100))
        self.assertEqual(core.rotated_size(100, 200, 270), (200, 100))

    def test_180_does_not_swap(self):
        self.assertEqual(core.rotated_size(100, 200, 180), (100, 200))


class TestComputeZoom(unittest.TestCase):
    def test_width_fit(self):
        self.assertEqual(core.compute_zoom("width", 1.0, 800, 600, 1600, 1200), 0.5)

    def test_height_fit(self):
        self.assertEqual(core.compute_zoom("height", 1.0, 800, 600, 1600, 1200), 0.5)

    def test_window_fit_uses_min(self):
        # 画布 800x600，图片 1600x1200 => min(0.5, 0.5)=0.5
        self.assertEqual(core.compute_zoom("window", 1.0, 800, 600, 1600, 1200), 0.5)
        # 画布 800x600，图片 800x1200（竖图）=> min(1.0, 0.5)=0.5
        self.assertEqual(core.compute_zoom("window", 1.0, 800, 600, 800, 1200), 0.5)

    def test_actual_fit(self):
        self.assertEqual(core.compute_zoom("actual", 3.0, 800, 600, 1600, 1200), 1.0)

    def test_custom_returns_zoom(self):
        self.assertEqual(core.compute_zoom("custom", 2.5, 800, 600, 1600, 1200), 2.5)

    def test_custom_clamped(self):
        self.assertEqual(core.compute_zoom("custom", 99.0, 800, 600, 1600, 1200), core.MAX_ZOOM)
        self.assertEqual(core.compute_zoom("custom", 0.001, 800, 600, 1600, 1200), core.MIN_ZOOM)

    def test_window_clamped_to_min_zoom(self):
        # 画布极小导致倍率低于 MIN_ZOOM 时应被钳制
        self.assertEqual(core.compute_zoom("window", 1.0, 1, 1, 1600, 1200), core.MIN_ZOOM)


class TestClampPan(unittest.TestCase):
    def test_no_pan_when_image_smaller(self):
        self.assertEqual(core.clamp_pan(10, 10, 800, 600, 400, 300, 1.0), (0, 0))

    def test_pan_allowed_when_zoomed(self):
        # 图片 1600x1200，zoom 1，画布 800x600：x 可平移 (1600-800)/2+60 = 460
        # y 可平移 (1200-600)/2+60 = 360
        px, py = core.clamp_pan(1000, 1000, 800, 600, 1600, 1200, 1.0)
        self.assertEqual(px, 460)
        self.assertEqual(py, 360)

    def test_pan_clamp_exact(self):
        # (1200-600)/2 + 60 = 360
        _, py = core.clamp_pan(0, 1000, 800, 600, 1600, 1200, 1.0)
        self.assertEqual(py, 360)

    def test_negative_pan_clamped(self):
        px, py = core.clamp_pan(-1000, -1000, 800, 600, 1600, 1200, 1.0)
        self.assertEqual(px, -460)
        self.assertEqual(py, -360)


class TestZoomAtPan(unittest.TestCase):
    def test_anchor_at_center(self):
        # 锚点在画布中心时，平移按 f 缩放
        px, py = core.zoom_at_pan(100, 50, 400, 300, 800, 600, 2.0)
        self.assertEqual(px, 200)
        self.assertEqual(py, 100)


class TestRegionZoomCrop(unittest.TestCase):
    def test_clamp_rz_center(self):
        self.assertEqual(core.clamp_rz_center(0.5, 0.5, 0.5), (0.5, 0.5))
        self.assertEqual(core.clamp_rz_center(0.0, 1.0, 0.5), (0.25, 0.75))
        self.assertEqual(core.clamp_rz_center(-9, 9, 0.1), (0.05, 0.95))

    def test_build_crop_geometry_center(self):
        # 320x180 视频，中心 50% 放大框
        # 注意 VLC 格式为「右下角 x 右下角 + 左上角 + 左上角」
        self.assertEqual(core.build_crop_geometry(320, 180, 0.5, 0.5, 0.5),
                         "240x135+80+45")

    def test_build_crop_geometry_topleft(self):
        self.assertEqual(core.build_crop_geometry(320, 180, 0.25, 0.25, 0.5),
                         "160x90+0+0")

    def test_build_crop_geometry_bottomright(self):
        self.assertEqual(core.build_crop_geometry(320, 180, 0.75, 0.75, 0.5),
                         "320x180+160+90")

    def test_build_crop_geometry_constant_size(self):
        """移动放大框时裁剪尺寸恒定（回归：曾因格式搞反导致移动变窄成条状）。"""
        w, h, scale = 320, 180, 0.5
        for cx in (0.25, 0.5, 0.75):
            for cy in (0.25, 0.5, 0.75):
                s = core.build_crop_geometry(w, h, cx, cy, scale)
                # 解析出右/下边界与左/上边界
                wh, xy = s.split("+", 1)
                right, bottom = (int(v) for v in wh.split("x"))
                left, top = (int(v) for v in xy.split("+"))
                self.assertEqual(right - left, 160)
                self.assertEqual(bottom - top, 90)


class TestZoomSlider(unittest.TestCase):
    def test_value_pos_roundtrip_image(self):
        lo, hi = core.MIN_ZOOM, core.MAX_ZOOM
        for z in (0.02, 0.5, 1.0, 2.48, 10.0, 40.0):
            pos = core.zoom_slider_pos(z, lo, hi)
            self.assertAlmostEqual(core.zoom_slider_value(pos, lo, hi), z, delta=z * 0.01 + 0.001)

    def test_video_range_mapping(self):
        # 视频范围 0.5x..4x
        self.assertEqual(core.zoom_slider_pos(0.5, 0.5, 4.0), 0)
        self.assertEqual(core.zoom_slider_pos(4.0, 0.5, 4.0), 1000)
        self.assertEqual(core.zoom_slider_pos(1.0, 0.5, 4.0), 333)

    def test_slider_value_monotonic(self):
        lo, hi = 0.5, 4.0
        vals = [core.zoom_slider_value(p, lo, hi) for p in range(0, 1001, 100)]
        self.assertEqual(vals, sorted(vals))


if __name__ == "__main__":
    unittest.main()
