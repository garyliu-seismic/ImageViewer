# -*- coding: utf-8 -*-
"""冒烟测试：启动 App + 打开图片 + 基本操作，确保重构后无回归。

需要图形环境（本机 Windows 可直接跑）。若在无显示环境会失败，属预期。
运行：  python tests/smoke_test.py
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import viewer_core as core
import image_viewer as iv
from PIL import Image


class SmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = iv.ComicViewer()
        cls.app.geometry("800x600")
        cls.app.update()
        # 造一张测试图
        cls.tmp = os.path.join(tempfile.gettempdir(), "iv_smoke_test.png")
        Image.new("RGB", (1200, 1600), (80, 120, 200)).save(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass
        try:
            os.remove(cls.tmp)
        except Exception:
            pass

    def _load_image(self):
        app = self.app
        app.sources = [self.tmp]
        app.index = 0
        app.is_video = False
        app.orig = app._open_image(self.tmp)
        app._spread_img = app._make_spread()
        app.update_idletasks()
        app._render()

    def test_app_launches_and_renders(self):
        self._load_image()
        self.assertTrue(self.app.orig is not None)
        self.assertTrue(self.app.zoom > 0)

    def test_compute_zoom_matches_core(self):
        self._load_image()
        app = self.app
        app.fit_mode = "window"
        rw, rh = app._rotated_size()
        cw = max(app.canvas.winfo_width(), 1)
        ch = max(app.canvas.winfo_height(), 1)
        expected = core.compute_zoom("window", app.zoom, cw, ch, rw, rh)
        app._render()
        self.assertAlmostEqual(app.zoom, expected)

    def test_fit_modes(self):
        self._load_image()
        app = self.app
        app.set_fit("actual")
        self.assertAlmostEqual(app.zoom, 1.0)
        app.set_fit("window")
        self.assertLessEqual(app.zoom, 1.0)

    def test_zoom_in_out_and_slider_sync(self):
        self._load_image()
        app = self.app
        app.set_fit("actual")
        z0 = app.zoom
        app.zoom_in()
        self.assertGreater(app.zoom, z0)
        app.zoom_out()
        self.assertAlmostEqual(app.zoom, z0)
        # 滑块位置与倍率往返一致
        lo, hi = core.MIN_ZOOM, core.MAX_ZOOM
        pos = app._zoom_slider_pos(app.zoom)
        self.assertAlmostEqual(app._zoom_slider_value(pos), app.zoom, delta=app.zoom * 0.01 + 0.001)

    def test_rotation_swaps_size(self):
        self._load_image()
        app = self.app
        w, h = app._rotated_size()
        self.assertEqual((w, h), (1200, 1600))
        app.rotation = 90
        self.assertEqual(app._rotated_size(), (1600, 1200))
        app.rotation = 0

    def test_region_zoom_crop_string(self):
        self._load_image()
        app = self.app
        app.rz.reset()
        # 模拟 320x180 视频：裁剪字符串应为「右下角x右下角+左上角+左上角」
        self.assertEqual(app.rz.crop_geometry(320, 180), "240x135+80+45")

    def test_clamp_pan_after_refactor(self):
        self._load_image()
        app = self.app
        app.set_fit("actual")  # zoom=1.0
        app.pan_x = app.pan_y = 10000
        app._clamp_pan()
        rw, rh = app._rotated_size()
        cw = max(app.canvas.winfo_width(), 1)
        ch = max(app.canvas.winfo_height(), 1)
        expected_x, expected_y = core.clamp_pan(10000, 10000, cw, ch, rw, rh, 1.0)
        self.assertAlmostEqual(app.pan_x, expected_x)
        self.assertAlmostEqual(app.pan_y, expected_y)


if __name__ == "__main__":
    unittest.main()
