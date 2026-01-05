"""最小测试：验证 ASRService 在配置 USE_REMOTE_ASR True/False 时策略类型切换。

运行方式（无 pytest 依赖）：
    python tests/test_asr_strategy_switch.py

只检查内部 _strategy 类型，不真正调用远程或本地模型推理，保证快速与无外部依赖（除已安装 dashscope）。
"""
from __future__ import annotations

import os
import sys

# 确保可以导入 core 包（若作为脚本直接运行）
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.asr_service import ASRService, RemoteASRStrategy, LocalASRStrategy  # type: ignore
from core.config import set_config_value  # type: ignore


def assert_isinstance(obj, cls, label: str):
    if not isinstance(obj, cls):
        raise AssertionError(f"{label} 期望类型 {cls.__name__} 实际为 {type(obj).__name__}")


def test_remote_strategy():
    """测试远程策略：设置 USE_REMOTE_ASR=True 后应选择 RemoteASRStrategy。"""
    set_config_value("USE_REMOTE_ASR", True)
    # 设置一个假 API Key，避免缺失导致初始化抛错（不做实际调用）
    set_config_value("DASHSCOPE_API_KEY", "sk-dummy-test")
    svc = ASRService()
    assert_isinstance(svc._strategy, RemoteASRStrategy, "远程策略切换失败")
    print("[OK] 远程策略切换验证通过")


def test_local_strategy():
    """测试本地策略：设置 USE_REMOTE_ASR=False 后应选择 LocalASRStrategy。"""
    set_config_value("USE_REMOTE_ASR", False)
    svc = ASRService()
    assert_isinstance(svc._strategy, LocalASRStrategy, "本地策略切换失败")
    print("[OK] 本地策略切换验证通过")


def main():
    failures = 0
    for fn in (test_remote_strategy, test_local_strategy):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"[FAIL] {fn.__name__}: {e}")
    if failures:
        print(f"总计 {failures} 个失败")
        sys.exit(1)
    print("所有切换测试通过")


if __name__ == "__main__":  # pragma: no cover
    main()
