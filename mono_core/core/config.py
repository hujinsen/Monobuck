"""统一配置加载：仅以 config.json 为来源。

要求：所有配置修改需直接编辑 config.json 或在进程内使用 set_config_value。
不再支持环境变量覆盖，避免双重来源导致的冲突与不可预期行为。
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict
import threading

_CONFIG_LOCK = threading.Lock()
_CONFIG_DATA: Dict[str, Any] = {}
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _load_file(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def reload_config() -> None:
    """重新加载配置（仅文件）。"""
    global _CONFIG_DATA
    with _CONFIG_LOCK:
        _CONFIG_DATA = _load_file(_CONFIG_PATH)


def get_config_value(key: str, default: Any = None) -> Any:
    return _CONFIG_DATA.get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """动态设置（仅进程内，不会写回文件）。"""
    with _CONFIG_LOCK:
        _CONFIG_DATA[key] = value


# 初始化加载
reload_config()

__all__ = [
    "reload_config",
    "get_config_value",
    "set_config_value",
]
