from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.services.assistant_rag import SourceChunk, answer_from_sources
from app.services.gemini_failover import call_gemini_with_failover

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedAssistantAnswer:
    text: str
    provider: str
    model: str
    used_fallback: bool = False


def _source_context(sources: list[SourceChunk]) -> str:
    sections: list[str] = []
    for index, source in enumerate(sources, start=1):
        occurred = (
            source.occurred_at.isoformat()
            if source.occurred_at
            else "unknown"
        )
        sections.append(
            "\n".join(
                [
                    f"[{index}]",
                    f"TYPE: {source.source_type}",
                    f"TITLE: {source.title}",
                    f"DATE: {occurred}",
                    f"CONTENT:\n{source.text}",
                ]
            )
        )
    return "\n\n---\n\n".join(sections)


def _gemini_prompt(question: str, sources: list[SourceChunk]) -> str:
    return f"""أنت "مساعد وئام"، مساعد تنسيق رعاية للأطفال ذوي الاحتياجات المختلفة.

مهمتك: الإجابة على سؤال المستخدم اعتمادًا حصريًا على المصادر المصرح بها أدناه.

قواعد إلزامية:
1) لا تستخدم أي معرفة خارج المصادر ولا تضف تشخيصًا أو علاجًا أو معلومة غير موجودة.
1.1) لا تصف ملاحظة صوتية أو ملخصًا آليًا أو استنتاجًا من النظام بأنه "تشخيص". قل مثلًا: "تذكر الملاحظة وجود..." أو "ورد في التقرير...". إذا كان المصدر تقريرًا طبيًا معتمدًا يحتوي تشخيصًا صريحًا من مختص، انسبه بوضوح إلى التقرير ولا تقدمه كتشخيص صادر منك.
2) إذا كانت المصادر لا تكفي، قل بوضوح إن المعلومات المعتمدة المتاحة غير كافية.
3) أجب بنفس لغة سؤال المستخدم. إذا كان السؤال بالعربية، حوّل المصطلحات التقنية البسيطة مثل completed وin_progress إلى عربية طبيعية، ولا تترجم أسماء الجهات أو القياسات الطبية إذا كان ذلك يغيّر معناها.
4) لخّص وافهم وادمج المعلومات؛ لا تنسخ كتلًا طويلة من المصادر. استخدم صياغة بشرية بسيطة ومباشرة.
5) اجعل الإجابة قصيرة جدًا وواضحة: سطر تمهيدي اختياري ثم 2-4 نقاط فقط. لا تتجاوز تقريبًا 90 كلمة إلا إذا طلب المستخدم تفاصيل.
6) ضع رقم المصدر بعد الادعاء المرتبط به بهذا الشكل [1] أو [2]. لا تستخدم رقم مصدر غير موجود.
7) إذا تكررت المعلومة في أكثر من مصدر، اذكرها مرة واحدة فقط.
8) عند وجود تحديثات متعارضة، فضّل الحالة الحالية/الأحدث زمنيًا، واذكر وجود تعارض إذا لم يمكن حسمه.
9) تجاهل عبارات الاختبار أو البيانات الوصفية مثل "Synthetic test document..." ما لم يسأل المستخدم عنها مباشرة.
10) إذا كان السؤال عن نوع محدد (تقرير/هدف/ملاحظة صوتية)، لا تتوسع إلى أنواع أخرى غير لازمة.
11) لا تقل إنك "طبيب" أو "تشخّص". اختم فقط عند الحاجة بتنبيه قصير جدًا أن الإجابة تنسيقية وليست تشخيصًا.

سؤال المستخدم:
{question}

المصادر المصرح بها:
{_source_context(sources)}

اكتب الإجابة فقط. استخدم هذا الشكل قدر الإمكان:
الخلاصة:
• نقطة قصيرة [1]
• نقطة قصيرة [2]
• نقطة قصيرة [3]

لا تكتب قائمة مراجع منفصلة، ولا تعِد عرض نص المصدر كاملًا لأن الواجهة ستعرض المصادر عند الطلب.
"""


def _extract_gemini_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )
    return "\n".join(
        str(part.get("text", "")).strip()
        for part in parts
        if part.get("text")
    ).strip()


SAFETY_NOTE = (
    "هذا مساعد تنسيقي يعتمد على بيانات الملف ولا يقدّم تشخيصًا طبيًا "
    "أو يغيّر خطة علاجية."
)


def _normalize_safety_note(text: str) -> str:
    """Keep one deterministic safety sentence regardless of Gemini wording."""
    lines = []
    for line in text.splitlines():
        clean = line.strip()
        # Remove Gemini's own alternative diagnostic disclaimer so the UI
        # does not show two nearly identical warnings.
        if "تشخيص" in clean and (
            clean.startswith("تنبيه")
            or "ليست تشخيص" in clean
            or "ليس تشخيص" in clean
            or "ليست بديلاً" in clean
            or "ليست بديلا" in clean
        ):
            continue
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    if SAFETY_NOTE not in cleaned:
        cleaned = f"{cleaned}\n\n{SAFETY_NOTE}".strip()
    return cleaned



def _normalize_arabic_for_match(value: str) -> str:
    return (
        value.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ة", "ه")
        .replace("ى", "ي")
        .strip()
    )


def _profile_section_values(source: SourceChunk, label: str) -> list[str]:
    prefix = f"{label}:"
    for line in source.text.splitlines():
        clean = line.strip()
        if clean.startswith(prefix):
            raw = clean[len(prefix):].strip()
            return [part.strip() for part in raw.split("|") if part.strip()]
    return []


def _ensure_structured_source_fidelity(
    *,
    question: str,
    text: str,
    sources: list[SourceChunk],
) -> str:
    """Preserve exact structured care-profile terms for focused questions.

    Gemini may naturally paraphrase values such as "دعم التواصل" into
    "دعم في التواصل". For structured profile fields, the recorded wording is
    meaningful and should remain visible exactly as stored.
    """
    normalized_question = _normalize_arabic_for_match(question)

    requested_sections: list[tuple[str, tuple[str, ...], str]] = [
        ("الاحتياجات", ("احتياج", "احتياجات"), "الاحتياجات المسجلة"),
        ("متطلبات الدعم", ("متطلبات الدعم", "دعم مطلوب"), "متطلبات الدعم المسجلة"),
        ("الخدمات الحالية", ("خدمات", "الخدمات"), "الخدمات الحالية"),
        ("الحالات", ("حاله", "حالات"), "الحالات المسجلة"),
    ]

    additions: list[str] = []
    for label, triggers, answer_label in requested_sections:
        if not any(
            _normalize_arabic_for_match(trigger) in normalized_question
            for trigger in triggers
        ):
            continue

        for index, source in enumerate(sources, start=1):
            if source.source_type != "profile":
                continue

            values = _profile_section_values(source, label)
            missing = [value for value in values if value not in text]
            if missing:
                additions.append(
                    f"• {answer_label}: {'، '.join(missing)} [{index}]"
                )
            break

    if not additions:
        return text

    safety = SAFETY_NOTE if SAFETY_NOTE in text else None
    body = text.replace(f"\n\n{SAFETY_NOTE}", "").strip() if safety else text.strip()

    body = f"{body}\n" + "\n".join(additions)
    if safety:
        body = f"{body}\n\n{SAFETY_NOTE}"
    return body.strip()



def generate_with_gemini(
    *,
    question: str,
    sources: list[SourceChunk],
) -> GeneratedAssistantAnswer:
    settings = get_settings()
    api_key = (settings.assistant_api_key or settings.ai_api_key or "").strip()
    if not api_key:
        raise RuntimeError("Gemini API key is not configured")

    primary_model = settings.assistant_model.strip() or "gemini-3.6-flash"
    if primary_model == "gemini-2.5-flash":
        primary_model = "gemini-3.6-flash"

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": _gemini_prompt(question, sources)}],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 2000,
            "thinkingConfig": {
                "thinkingLevel": "low"
            },
        },
    }

    result = call_gemini_with_failover(
        api_key=api_key,
        primary_model=primary_model,
        body=body,
        timeout_seconds=settings.assistant_timeout_seconds,
        post_func=httpx.post,
    )

    text = _extract_gemini_text(result.payload)
    if not text:
        raise RuntimeError("Gemini returned an empty answer")

    normalized_text = _normalize_safety_note(text)
    normalized_text = _ensure_structured_source_fidelity(
        question=question,
        text=normalized_text,
        sources=sources,
    )

    return GeneratedAssistantAnswer(
        text=normalized_text,
        provider="gemini",
        model=result.model,
        used_fallback=result.used_secondary,
    )


def generate_grounded_answer(
    *,
    question: str,
    sources: list[SourceChunk],
) -> GeneratedAssistantAnswer:
    settings = get_settings()
    provider = settings.assistant_provider.strip().lower()

    if provider == "gemini" and sources:
        try:
            return generate_with_gemini(
                question=question,
                sources=sources,
            )
        except Exception as exc:
            # Free-tier quota/network/key problems must never break the feature.
            logger.warning("Gemini assistant fallback activated: %s", exc)

    return GeneratedAssistantAnswer(
        text=answer_from_sources(question, sources),
        provider="local_grounded_retrieval",
        model="weam-grounded-rag-v2",
        used_fallback=(provider == "gemini"),
    )
