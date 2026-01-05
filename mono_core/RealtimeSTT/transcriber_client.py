"""转写客户端封装

该模块将主进程与转写子进程之间的通信封装成一个类，
让 AudioToTextRecorder 只通过简单的方法发送音频、轮询结果，
而不用直接管理 Pipe、Event 和 Process。
"""

from __future__ import annotations

import logging
from typing import Tuple, Any

import torch.multiprocessing as mp

try:  # 包内相对导入
    from .transcription_worker import run_transcription_worker
except ImportError:  # 直接在 RealtimeSTT 目录下运行脚本时的退化导入
    from transcription_worker import run_transcription_worker


class SenseVoiceTranscriber:
    """SenseVoice 模型的转写客户端

    - 在独立子进程中加载和运行 SenseVoice 模型
    - 通过 Pipe 发送 (audio, language) 并接收 (status, text)
    - 对外提供简单的 send/poll/recv 接口
    """

    def __init__(self, model_path: str,
                 shutdown_event: mp.Event,
                 interrupt_stop_event: mp.Event) -> None:
        self.model_path = model_path
        self.shutdown_event = shutdown_event
        self.interrupt_stop_event = interrupt_stop_event

        self.ready_event = mp.Event()
        self.parent_pipe, child_pipe = mp.Pipe()
        self.parent_stdout_pipe, child_stdout_pipe = mp.Pipe()

        self.process = mp.Process(
            target=run_transcription_worker,
            args=(
                child_pipe,
                child_stdout_pipe,
                self.model_path,
                self.ready_event,
                self.shutdown_event,
                self.interrupt_stop_event,
            ),
            daemon=True,
        )
        self.process.start()

        logging.debug("等待 SenseVoice 转写子进程加载模型...")
        self.ready_event.wait()
        logging.debug("SenseVoice 转写子进程已就绪")

    # 基本通信接口 ---------------------------------------------------------
    def send(self, audio: Any, language: str) -> None:
        """发送一次转写请求"""
        self.parent_pipe.send((audio, language))

    def poll(self, timeout: float) -> bool:
        """在给定超时时间内轮询是否有转写结果可读"""
        return self.parent_pipe.poll(timeout)

    def recv(self) -> Tuple[str, str]:
        """接收一次转写结果，返回 (status, text_or_error)"""
        return self.parent_pipe.recv()

    # 资源访问 -------------------------------------------------------------
    @property
    def stdout_pipe(self):
        """向外暴露 stdout Pipe，供主进程读取子进程日志"""
        return self.parent_stdout_pipe

    # 关闭与清理 -----------------------------------------------------------
    def close(self, timeout: float = 10.0) -> None:
        """优雅关闭子进程与相关资源"""
        logging.debug("准备关闭 SenseVoice 转写子进程")
        try:
            self.shutdown_event.set()
            self.process.join(timeout=timeout)
            if self.process.is_alive():
                logging.warning("转写子进程未在超时时间内退出，将强制终止")
                self.process.terminate()
        except Exception as e:  # noqa: BLE001
            logging.error("关闭转写子进程时发生异常: %s", e, exc_info=True)
        finally:
            try:
                self.parent_pipe.close()
            except Exception:
                pass
            try:
                self.parent_stdout_pipe.close()
            except Exception:
                pass
