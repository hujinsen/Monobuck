import datetime
import json
from pathlib import Path
import sys
from typing import Any, cast, Iterator, Dict

# 确保可以找到 core 包
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.asr_service import ASRService  # type: ignore
from core.config import set_config_value, get_config_value  # type: ignore


class _FakeStreamStrategy:
    def transcribe_stream(self, audio_stream: Iterator[bytes]):
        first = True
        accumulated = b""
        for chunk in audio_stream:
            accumulated += chunk
            if first:
                first = False
                yield {"text": "hello", "is_final": False, "raw_chunk": chunk}
        # final
        yield {"text": "hello world", "is_final": True, "raw_chunk": b""}

    def transcribe_file(self, path: str) -> str:  # pragma: no cover
        return "dummy"

    def transcribe_microphone(self):  # pragma: no cover
        yield {"text": "dummy", "is_final": True}


def _iter_pcm_chunks():
    # two chunks of silence (16kHz 100ms -> 1600 samples -> 3200 bytes)
    chunk = bytes([0]) * 3200
    for _ in range(2):
        yield chunk


def test_stream_persistence_finalize():
    # ensure persistence enabled
    set_config_value("PERSIST_ENABLE", True)
    svc = ASRService()
    # monkeypatch strategy to avoid heavy model/network
    svc._strategy = cast(Any, _FakeStreamStrategy())  # type: ignore[attr-defined]
    svc.strategy_name = "fake-asr"
    # run finalize (blocking) persistence
    final_text = svc.transcribe_stream_finalize(_iter_pcm_chunks())
    assert final_text == "hello world"
    # locate today's directory
    persist_dir = Path(get_config_value("PERSIST_DIR"))
    date_dir = persist_dir / datetime.date.today().isoformat()
    assert date_dir.exists(), f"Date directory not created: {date_dir}"
    json_files = sorted([p for p in date_dir.glob("*.json")])
    assert json_files, "No JSON session file generated"
    # read last JSON
    with json_files[-1].open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("asr_phase", {}).get("text") == "hello world"
    audio_meta = data.get("audio", {})
    assert audio_meta.get("channels") == 1
    assert audio_meta.get("sample_rate") == 16000


def test_stream_persistence_incremental():
    set_config_value("PERSIST_ENABLE", True)
    svc = ASRService()
    svc._strategy = cast(Any, _FakeStreamStrategy())  # type: ignore[attr-defined]
    svc.strategy_name = "fake-asr"
    gen = svc.transcribe_stream_with_persist(_iter_pcm_chunks(), persist=True)
    parts = []
    try:
        for part in gen:
            parts.append(part)
    except StopIteration as e:
        final_text = e.value
    else:
        # generator will raise StopIteration with return value; emulate by exhausting
        final_text = gen.send(None)  # type: ignore
    assert parts and parts[0]["text"] == "hello" and not parts[0]["is_final"]
    # final_text produced at completion
    assert "hello world" in (final_text or "")
    # verify new session
    persist_dir = Path(get_config_value("PERSIST_DIR"))
    date_dir = persist_dir / datetime.date.today().isoformat()
    json_files = sorted([p for p in date_dir.glob("*.json")])
    assert json_files, "No JSON session file generated (incremental)"
    # open last
    with json_files[-1].open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("asr_phase", {}).get("text") == "hello world"
