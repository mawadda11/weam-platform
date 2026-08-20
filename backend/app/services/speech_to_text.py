from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.core.config import get_settings


class SpeechToTextError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpeechToTextResult:
    provider: str
    model: str
    language: str
    transcript: str


_model_cache: dict[tuple[str, str, str], object] = {}
_pipeline_cache: dict[tuple[str, str, str], object] = {}
_model_lock = Lock()


def _load_local_model(*, model_name: str, device: str, compute_type: str):
    key = (model_name, device, compute_type)
    if key in _model_cache:
        return _model_cache[key]

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise SpeechToTextError(
            "faster-whisper is not installed. Run: pip install -r requirements.txt"
        ) from exc

    with _model_lock:
        if key not in _model_cache:
            _model_cache[key] = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
            )
    return _model_cache[key]


def _get_batched_pipeline(*, model_name: str, device: str, compute_type: str):
    key = (model_name, device, compute_type)
    if key in _pipeline_cache:
        return _pipeline_cache[key]

    try:
        from faster_whisper import BatchedInferencePipeline
    except ImportError as exc:
        raise SpeechToTextError(
            "Your faster-whisper version does not provide batched inference"
        ) from exc

    model = _load_local_model(
        model_name=model_name,
        device=device,
        compute_type=compute_type,
    )
    with _model_lock:
        if key not in _pipeline_cache:
            _pipeline_cache[key] = BatchedInferencePipeline(model=model)
    return _pipeline_cache[key]


def _transcribe_with_model(*, path: Path, model_name: str) -> SpeechToTextResult:
    settings = get_settings()
    language = (settings.stt_language or "").strip().lower()
    language_arg = None if language in {"", "auto"} else language

    pipeline = _get_batched_pipeline(
        model_name=model_name,
        device=settings.stt_device,
        compute_type=settings.stt_compute_type,
    )

    try:
        segments, info = pipeline.transcribe(
            str(path),
            language=language_arg,
            beam_size=max(1, settings.stt_beam_size),
            batch_size=max(1, settings.stt_batch_size),
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": max(
                    100, settings.stt_vad_min_silence_ms
                )
            },
            condition_on_previous_text=False,
        )
        pieces = [
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ]
    except Exception as exc:
        raise SpeechToTextError(
            f"Local Whisper transcription failed with '{model_name}': {exc}"
        ) from exc

    transcript = " ".join(pieces).strip()
    if not transcript:
        raise SpeechToTextError("Local Whisper returned an empty transcript")

    detected_language = (
        language_arg
        or getattr(info, "language", None)
        or "unknown"
    )

    return SpeechToTextResult(
        provider="local_whisper",
        model=model_name,
        language=detected_language,
        transcript=transcript,
    )


def _local_whisper_transcribe(*, path: Path) -> SpeechToTextResult:
    settings = get_settings()
    preferred = settings.stt_model.strip() or "large-v3-turbo"
    fallback = settings.stt_fallback_model.strip() or "small"

    try:
        return _transcribe_with_model(path=path, model_name=preferred)
    except SpeechToTextError as preferred_error:
        # If a bigger model cannot load on a lower-memory laptop, keep the
        # feature usable for the demo by falling back to the smaller model.
        if fallback and fallback != preferred:
            try:
                return _transcribe_with_model(path=path, model_name=fallback)
            except SpeechToTextError:
                pass
        raise preferred_error


def transcribe_audio(
    *,
    path: Path,
    title: str,
) -> SpeechToTextResult:
    settings = get_settings()
    provider = settings.stt_provider.strip().lower()

    if provider == "mock":
        return SpeechToTextResult(
            provider="mock",
            model="weam-local-stt-workflow-v1",
            language=settings.stt_language or "ar",
            transcript=(
                f"هذه مسودة تفريغ تجريبية للملاحظة الصوتية «{title}». "
                "تم إنشاؤها في وضع التطوير المحلي لاختبار التسجيل والمراجعة "
                "والاعتماد، وليست ناتجة عن تعرف فعلي على محتوى الصوت."
            ),
        )

    if provider == "local_whisper":
        return _local_whisper_transcribe(path=path)

    raise SpeechToTextError(
        f"Speech-to-text provider '{provider}' is not configured in this build"
    )
