from dataclasses import dataclass
from typing import Protocol

import numpy as np
from scipy import signal
import torch

INT16_MAX_ABS_VALUE = 32768.0


class SileroVadModel(Protocol):
    def __call__(self, audio, sample_rate: int):  # type: ignore[override]
        ...


class WebRtcVadModel(Protocol):
    def is_speech(self, frame: bytes, sample_rate: int) -> bool:  # pragma: no cover - protocol
        ...


@dataclass
class VadConfig:
    sample_rate: int
    silero_sensitivity: float


def silero_is_speech(model: SileroVadModel,
                     chunk: bytes,
                     cfg: VadConfig) -> bool:
    """Pure Silero VAD check.

    - Optionally resamples incoming audio to 16k
    - Normalizes to float32 and forwards through model
    - Returns boolean speech flag
    """
    pcm_data = np.frombuffer(chunk, dtype=np.int16)
    if cfg.sample_rate != 16000:
        data_16000 = signal.resample_poly(pcm_data, 16000, cfg.sample_rate)
        pcm_data = data_16000.astype(np.int16)

    audio_chunk = pcm_data.astype(np.float32) / INT16_MAX_ABS_VALUE
    vad_prob = model(torch.from_numpy(audio_chunk), 16000).item()
    return vad_prob > (1 - cfg.silero_sensitivity)


def webrtc_is_speech(model: WebRtcVadModel,
                     chunk: bytes,
                     sample_rate: int,
                     all_frames_must_be_true: bool = False) -> bool:
    """Pure WebRTC VAD check over a 10ms-frame window."""
    if sample_rate != 16000:
        pcm_data = np.frombuffer(chunk, dtype=np.int16)
        data_16000 = signal.resample_poly(pcm_data, 16000, sample_rate)
        chunk = data_16000.astype(np.int16).tobytes()

    frame_length = int(16000 * 0.01)  # 10 ms frame
    num_frames = int(len(chunk) / (2 * frame_length))
    if num_frames == 0:
        return False

    speech_frames = 0
    for i in range(num_frames):
        start_byte = i * frame_length * 2
        end_byte = start_byte + frame_length * 2
        frame = chunk[start_byte:end_byte]
        if model.is_speech(frame, 16000):
            speech_frames += 1
            if not all_frames_must_be_true:
                return True

    if all_frames_must_be_true:
        return speech_frames == num_frames

    return False
