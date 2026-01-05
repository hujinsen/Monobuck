from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable


class RecorderState(str, Enum):
    INACTIVE = "inactive"
    LISTENING = "listening"
    WAKEWORD = "wakeword"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"


@dataclass
class StateCallbacks:
    on_vad_detect_start: Optional[Callable[[], None]] = None
    on_vad_detect_stop: Optional[Callable[[], None]] = None
    on_wakeword_detection_start: Optional[Callable[[], None]] = None
    on_wakeword_detection_end: Optional[Callable[[], None]] = None
    on_transcription_start: Optional[Callable[[], None]] = None


def transition_state(owner,
                     new_state: RecorderState,
                     callbacks: StateCallbacks,
                     spinner_enabled: bool = True,
                     wake_words: str = "") -> None:
    """Centralized state transition helper.

    This keeps all side effects of state changes (callbacks + spinner text)
    in one place so that threading / process code does not duplicate logic.

    The *owner* is expected to provide:
    - .state: current state string
    - .halo: optional Halo spinner instance or None
    - ._set_spinner(text: str): method to update/create spinner text
    - .spinner: bool flag whether spinner is enabled

    The API matches the existing behaviour of AudioToTextRecorder._set_state.

    集中式状态切换辅助函数

    该函数统一管理状态变更时的所有副作用操作（如回调触发、Spinner 文本更新），
    避免在多线程或进程代码中重复实现相同逻辑，确保行为一致、易于维护。
    """
    import logging

    old_state = getattr(owner, "state", None)
    if old_state == new_state.value:
        return

    setattr(owner, "state", new_state.value)
    logging.info("State changed from '%s' to '%s'", old_state, new_state.value)

    # FROM-state callbacks
    if old_state == RecorderState.LISTENING.value:
        if callbacks.on_vad_detect_stop:
            callbacks.on_vad_detect_stop()
    elif old_state == RecorderState.WAKEWORD.value:
        if callbacks.on_wakeword_detection_end:
            callbacks.on_wakeword_detection_end()

    # TO-state callbacks + spinner
    halo = getattr(owner, "halo", None)

    if new_state == RecorderState.LISTENING:
        if callbacks.on_vad_detect_start:
            callbacks.on_vad_detect_start()
        owner._set_spinner("speak now")
        if spinner_enabled and halo:
            halo._interval = 250

    elif new_state == RecorderState.WAKEWORD:
        if callbacks.on_wakeword_detection_start:
            callbacks.on_wakeword_detection_start()
        owner._set_spinner(f"say {wake_words}")
        if spinner_enabled and halo:
            halo._interval = 500

    elif new_state == RecorderState.TRANSCRIBING:
        if callbacks.on_transcription_start:
            callbacks.on_transcription_start()
        owner._set_spinner("transcribing")
        if spinner_enabled and halo:
            halo._interval = 50

    elif new_state == RecorderState.RECORDING:
        owner._set_spinner("recording")
        if spinner_enabled and halo:
            halo._interval = 100

    elif new_state == RecorderState.INACTIVE:
        if spinner_enabled and halo:
            halo.stop()
            owner.halo = None
