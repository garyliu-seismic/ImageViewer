# -*- coding: utf-8 -*-
"""配置读写（image_viewer.json 的 load/save，纯逻辑，无 UI 依赖）。"""

import json


def load_config(path):
    """读取 JSON 配置；失败返回空 dict。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(path, config):
    """写回 JSON 配置；失败静默忽略（与当前行为一致）。"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
