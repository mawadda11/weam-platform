from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings


class SpeechToTextError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpeechToTextResult:
    provider: str
    model: str
    language: str
    transcript: str


def transcribe_audio(
    *,
    path: Path,
    title: str,
) -> SpeechToTextResult:
    settings = get_settings()
    provider = settings.stt_provider.strip().lower()

    if provider == "mock":
        # Deliberately explicit: this tests the complete product workflow
        # without pretending local development performed real speech recognition.
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

    raise SpeechToTextError(
        f"Speech-to-text provider '{provider}' is not configured in this build"
    )
