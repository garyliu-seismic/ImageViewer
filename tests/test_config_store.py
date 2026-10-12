# -*- coding: utf-8 -*-
"""config_store 纯逻辑单元测试。"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config_store as cs


class TestConfigStore(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)

    def tearDown(self):
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_roundtrip(self):
        cs.save_config(self.path, {"a": 1, "b": [True, None, "x"]})
        self.assertEqual(cs.load_config(self.path), {"a": 1, "b": [True, None, "x"]})

    def test_load_missing_returns_empty(self):
        self.assertEqual(cs.load_config(self.path + ".nope"), {})

    def test_load_invalid_json_returns_empty(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{invalid")
        self.assertEqual(cs.load_config(self.path), {})


if __name__ == "__main__":
    unittest.main()
