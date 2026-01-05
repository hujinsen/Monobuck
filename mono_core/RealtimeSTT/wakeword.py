from __future__ import annotations

"""唤醒词检测模块

本文件将具体的唤醒词实现（Porcupine / OpenWakeWord）从
AudioToTextRecorder 中抽离出来，符合单一职责原则：

- AudioToTextRecorder 只依赖抽象接口 IWakeWordDetector
- 具体使用哪种唤醒词引擎，由这里的实现类决定
"""

from dataclasses import dataclass
from typing import List, Protocol

import numpy as np
import struct

import openwakeword
from openwakeword.model import Model
import pvporcupine


class IWakeWordDetector(Protocol):
    """唤醒词检测接口

    返回值为被触发的唤醒词索引：
    - >= 0 表示检测到了第 index 个唤醒词
    - < 0 表示本次数据未检测到唤醒词
    """

    def process(self, data: bytes) -> int:  # pragma: no cover - protocol
        ...


@dataclass
class PorcupineWakeWordDetector(IWakeWordDetector):
    """基于 pvporcupine 的唤醒词检测实现"""

    keywords: List[str]
    sensitivities: List[float]

    def __post_init__(self) -> None:
        # 创建 Porcupine 引擎实例
        self._engine = pvporcupine.create(
            keywords=self.keywords,
            sensitivities=self.sensitivities,
        )

    @property
    def frame_length(self) -> int:
        """每次需要的采样点数量（采样为 16bit 整数，字节数为 frame_length * 2）"""

        return self._engine.frame_length

    @property
    def sample_rate(self) -> int:
        """引擎要求的采样率（Hz）"""

        return self._engine.sample_rate

    def process(self, data: bytes) -> int:
        """对一帧 PCM 数据进行唤醒词检测"""

        if len(data) < self._engine.frame_length * 2:
            return -1
        pcm = struct.unpack_from("h" * self._engine.frame_length, data)
        return self._engine.process(pcm)


@dataclass
class OpenWakeWordDetector(IWakeWordDetector):
    """基于 OpenWakeWord 的唤醒词检测实现"""

    model_paths: List[str] | None = None
    framework: str = "onnx"
    sensitivity: float = 0.5

    def __post_init__(self) -> None:
        # 确保模型已下载
        openwakeword.utils.download_models()
        if self.model_paths:
            self._model = Model(
                wakeword_models=self.model_paths,
                inference_framework=self.framework,
            )
        else:
            self._model = Model(inference_framework=self.framework)

    def process(self, data: bytes) -> int:
        """对一段 PCM 数据进行唤醒词检测，返回触发索引"""

        pcm = np.frombuffer(data, dtype=np.int16)
        if pcm.size == 0:
            return -1

        # 更新内部预测缓存
        self._model.predict(pcm)

        max_score = -1.0
        max_index = -1
        for idx, mdl in enumerate(self._model.prediction_buffer.keys()):
            scores = list(self._model.prediction_buffer[mdl])
            if not scores:
                continue
            if scores[-1] >= self.sensitivity and scores[-1] > max_score:
                max_score = scores[-1]
                max_index = idx

        return max_index
