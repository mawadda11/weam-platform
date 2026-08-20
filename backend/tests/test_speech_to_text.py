from pathlib import Path
from types import SimpleNamespace

from app.services import speech_to_text


class FakeSegment:
    def __init__(self, text: str):
        self.text = text


class FakePipeline:
    def transcribe(self, path, **kwargs):
        assert Path(path).name == "sample.wav"
        assert kwargs["language"] is None
        assert kwargs["beam_size"] == 1
        assert kwargs["batch_size"] == 4
        assert kwargs["vad_filter"] is True
        return (
            iter([FakeSegment("السلام عليكم"), FakeSegment("Hello Weam")]),
            SimpleNamespace(language="ar"),
        )


def test_balanced_local_whisper_uses_batching(tmp_path, monkeypatch):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 64)

    settings = SimpleNamespace(
        stt_model="large-v3-turbo",
        stt_fallback_model="small",
        stt_language="auto",
        stt_device="cpu",
        stt_compute_type="int8",
        stt_batch_size=4,
        stt_beam_size=1,
        stt_vad_min_silence_ms=500,
    )
    monkeypatch.setattr(speech_to_text, "get_settings", lambda: settings)
    monkeypatch.setattr(
        speech_to_text,
        "_get_batched_pipeline",
        lambda **kwargs: FakePipeline(),
    )

    result = speech_to_text._local_whisper_transcribe(path=audio)
    assert result.provider == "local_whisper"
    assert result.model == "large-v3-turbo"
    assert result.language == "ar"
    assert result.transcript == "السلام عليكم Hello Weam"
