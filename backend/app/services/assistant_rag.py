from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.constants import CarePermission
from app.models.child import Child
from app.models.goal import Goal
from app.models.report import Report
from app.models.report_ai import ReportAIAnalysis
from app.models.user import User
from app.models.voice_note import VoiceNote
from app.services.access import AccessGrant


ARABIC_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0670\u06D6-\u06ED]")
NON_WORD = re.compile(r"[^\w\u0600-\u06FF]+", re.UNICODE)

STOPWORDS = {
    "في", "من", "على", "الى", "إلى", "عن", "ما", "ماذا", "هل", "كيف",
    "هو", "هي", "هذا", "هذه", "ذلك", "التي", "الذي", "مع", "او", "أو",
    "and", "or", "the", "is", "are", "of", "to", "for", "what", "how",
    "child", "الطفل", "الطفلة",
}

Intent = Literal[
    "summary",
    "goals",
    "reports",
    "voice",
    "follow_up",
    "needs",
    "general",
]


@dataclass
class SourceChunk:
    source_type: str
    source_id: str
    title: str
    text: str
    occurred_at: datetime | None = None


def _normalize(text: str) -> str:
    value = ARABIC_DIACRITICS.sub("", text.lower())
    value = (
        value.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ى", "ي")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
        .replace("ة", "ه")
    )
    value = NON_WORD.sub(" ", value)
    return " ".join(value.split())


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in _normalize(text).split()
        if len(token) > 1 and token not in STOPWORDS
    ]


def detect_intent(question: str) -> Intent:
    q = _normalize(question)

    if any(term in q for term in ["صوت", "صوتيه", "ملاحظه صوتيه", "voice", "audio"]):
        return "voice"
    if any(term in q for term in ["هدف", "اهداف", "تقدم", "نسبه", "goal", "progress"]):
        return "goals"
    if any(term in q for term in ["تقرير", "تقارير", "report", "نتائج", "result"]):
        if any(term in q for term in ["متابعه", "التالي", "القادمه", "follow", "next"]):
            return "follow_up"
        return "reports"
    if any(term in q for term in ["متابعه", "التالي", "القادمه", "follow", "next", "موعد"]):
        return "follow_up"
    if any(term in q for term in ["احتياج", "احتياجات", "يحتاج", "need", "support"]):
        return "needs"
    if any(term in q for term in ["ملخص", "لخص", "اجمع", "شامل", "summary", "الوضع", "الحاله", "الحالة"]):
        return "summary"
    return "general"


def _visible_report(report: Report, user: User, grant: AccessGrant) -> bool:
    if grant.is_primary_guardian:
        return True
    if report.visibility == "care_team":
        return True
    return user.id in (report.allowed_user_ids or [])


def _clean_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        " ".join(item.strip().split())
        for item in value
        if isinstance(item, str) and item.strip()
    ]


def _join_sections(sections: list[tuple[str, str | list[str] | None]]) -> str:
    output: list[str] = []
    for label, value in sections:
        if isinstance(value, list):
            parts = [item for item in value if item]
            if parts:
                output.append(f"{label}: " + " | ".join(parts))
        elif isinstance(value, str) and value.strip():
            output.append(f"{label}: {' '.join(value.strip().split())}")
    return "\n".join(output)


def collect_authorized_sources(
    db: Session,
    *,
    child_id: str,
    user: User,
    grant: AccessGrant,
) -> list[SourceChunk]:
    """Build one coherent chunk per real source to avoid citation/card duplication."""
    chunks: list[SourceChunk] = []

    child = db.scalar(
        select(Child)
        .options(
            selectinload(Child.identity),
            selectinload(Child.care_profile),
        )
        .where(Child.id == child_id)
    )
    if child and child.care_profile:
        profile = child.care_profile
        name = (
            child.identity.preferred_name
            if child.identity and child.identity.preferred_name
            else child.identity.first_name
            if child.identity
            else "الطفل"
        )
        profile_text = _join_sections(
            [
                ("الحالات", _clean_list(profile.conditions)),
                ("الاحتياجات", _clean_list(profile.needs)),
                ("متطلبات الدعم", _clean_list(profile.support_requirements)),
                ("الخدمات الحالية", _clean_list(profile.services)),
                ("ملخص الملف", profile.summary or ""),
            ]
        )
        if profile_text:
            chunks.append(
                SourceChunk(
                    source_type="profile",
                    source_id=child.id,
                    title=f"ملف {name}",
                    text=profile_text,
                    occurred_at=child.updated_at,
                )
            )

    if grant.allows(CarePermission.VIEW_REPORTS.value):
        reports = db.scalars(
            select(Report).where(
                Report.child_id == child_id,
                Report.is_archived.is_(False),
            )
        ).all()
        visible_reports = {
            report.id: report
            for report in reports
            if _visible_report(report, user, grant)
        }

        if visible_reports:
            analyses = db.scalars(
                select(ReportAIAnalysis)
                .where(
                    ReportAIAnalysis.child_id == child_id,
                    ReportAIAnalysis.analysis_status == "completed",
                    ReportAIAnalysis.review_status == "approved",
                )
                .order_by(ReportAIAnalysis.created_at.desc())
            ).all()

            # Keep only the latest approved analysis for each visible report.
            seen_reports: set[str] = set()
            for analysis in analyses:
                if analysis.report_id not in visible_reports:
                    continue
                if analysis.report_id in seen_reports:
                    continue
                seen_reports.add(analysis.report_id)

                report = visible_reports[analysis.report_id]
                result = analysis.result_json or {}
                report_text = _join_sections(
                    [
                        ("الملخص", result.get("summary")),
                        ("أهم النتائج", _clean_list(result.get("key_findings"))),
                        ("الاحتياجات", _clean_list(result.get("needs"))),
                        ("التوصيات", _clean_list(result.get("recommendations"))),
                        ("إجراءات المتابعة", _clean_list(result.get("follow_up_actions"))),
                        ("الأهداف المذكورة", _clean_list(result.get("goal_mentions"))),
                    ]
                )
                if report_text:
                    chunks.append(
                        SourceChunk(
                            source_type="report",
                            source_id=report.id,
                            title=f"تقرير معتمد · {report.title}",
                            text=report_text,
                            occurred_at=analysis.reviewed_at or analysis.created_at,
                        )
                    )

    if grant.allows(CarePermission.VIEW_GOALS.value):
        goals = db.scalars(
            select(Goal)
            .options(selectinload(Goal.updates))
            .where(Goal.child_id == child_id)
            .order_by(Goal.updated_at.desc())
        ).all()
        for goal in goals:
            latest_update = goal.updates[-1] if goal.updates else None
            sections: list[tuple[str, str | list[str] | None]] = [
                ("الهدف", goal.title),
                ("الحالة الحالية", goal.status),
                ("نسبة التقدم الحالية", f"{goal.progress_percent}%"),
                ("الوصف", goal.description),
                ("التصنيف", goal.category),
                (
                    "التاريخ المستهدف",
                    goal.target_date.isoformat() if goal.target_date else None,
                ),
            ]
            if latest_update:
                sections.extend(
                    [
                        (
                            "آخر تحديث",
                            latest_update.note or "لا توجد ملاحظة نصية",
                        ),
                        (
                            "قيمة آخر تحديث",
                            f"{latest_update.progress_percent}% / {latest_update.status}",
                        ),
                    ]
                )
            chunks.append(
                SourceChunk(
                    source_type="goal",
                    source_id=goal.id,
                    title=f"هدف · {goal.title}",
                    text=_join_sections(sections),
                    occurred_at=goal.updated_at,
                )
            )

    if grant.allows(CarePermission.VIEW_VOICE_NOTES.value):
        notes = db.scalars(
            select(VoiceNote)
            .where(
                VoiceNote.child_id == child_id,
                VoiceNote.is_archived.is_(False),
                VoiceNote.review_status == "approved",
            )
            .order_by(VoiceNote.created_at.desc())
        ).all()
        for note in notes:
            if note.transcript_final:
                chunks.append(
                    SourceChunk(
                        source_type="voice",
                        source_id=note.id,
                        title=f"ملاحظة صوتية معتمدة · {note.title}",
                        text=note.transcript_final,
                        occurred_at=note.reviewed_at or note.created_at,
                    )
                )

    return chunks


def _score(query_tokens: list[str], chunk: SourceChunk, now: datetime) -> float:
    chunk_tokens = _tokens(f"{chunk.title} {chunk.text}")
    if not chunk_tokens:
        return 0.0

    qset = set(query_tokens)
    cset = set(chunk_tokens)
    overlap = len(qset & cset)
    coverage = overlap / max(1, len(qset))

    fuzzy = 0
    for q in qset:
        if len(q) < 4:
            continue
        if any(c.startswith(q[:4]) or q.startswith(c[:4]) for c in cset):
            fuzzy += 1

    recency = 0.0
    if chunk.occurred_at:
        occurred = chunk.occurred_at
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - occurred).total_seconds() / 86400)
        recency = 1 / (1 + math.log1p(age_days))

    return overlap * 3.0 + coverage * 4.0 + fuzzy * 0.7 + recency * 0.5


def _allowed_source_types(intent: Intent) -> set[str] | None:
    mapping = {
        "voice": {"voice"},
        "goals": {"goal"},
        "reports": {"report"},
        "follow_up": {"report", "goal", "voice"},
        "needs": {"profile", "report", "voice"},
        "summary": None,
        "general": None,
    }
    return mapping[intent]


def _dedupe(chunks: Iterable[SourceChunk]) -> list[SourceChunk]:
    seen: set[tuple[str, str]] = set()
    result: list[SourceChunk] = []
    for chunk in chunks:
        key = (chunk.source_type, chunk.source_id)
        if key not in seen:
            seen.add(key)
            result.append(chunk)
    return result


def retrieve(
    question: str,
    chunks: Iterable[SourceChunk],
    *,
    limit: int = 5,
) -> list[SourceChunk]:
    now = datetime.now(timezone.utc)
    intent = detect_intent(question)
    allowed = _allowed_source_types(intent)

    candidates = [
        chunk
        for chunk in _dedupe(chunks)
        if allowed is None or chunk.source_type in allowed
    ]
    if not candidates:
        return []

    query_tokens = _tokens(question)
    ranked = sorted(
        candidates,
        key=lambda chunk: _score(query_tokens, chunk, now),
        reverse=True,
    )

    # For summaries, force source diversity instead of taking five fragments
    # from the same category.
    if intent == "summary":
        selected: list[SourceChunk] = []
        used_types: set[str] = set()
        for source_type in ("profile", "report", "goal", "voice"):
            typed = [chunk for chunk in ranked if chunk.source_type == source_type]
            if typed:
                selected.append(typed[0])
                used_types.add(source_type)
            if len(selected) >= limit:
                break
        for chunk in ranked:
            if len(selected) >= limit:
                break
            if chunk not in selected:
                selected.append(chunk)
        return selected[:limit]

    # Questions tied to a single source family should not be padded with
    # unrelated sources just to reach the configured limit.
    positive = [
        chunk
        for chunk in ranked
        if _score(query_tokens, chunk, now) > 0.45
    ]
    if positive:
        return positive[:limit]
    return ranked[: min(limit, 2)]


def _section_map(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for line in text.splitlines():
        clean = line.strip()
        if not clean or ":" not in clean:
            continue
        key, value = clean.split(":", 1)
        sections[key.strip()] = value.strip()
    return sections


def _short(value: str | None, limit: int = 170) -> str:
    if not value:
        return ""
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _translate_status(value: str) -> str:
    mapping = {
        "completed": "مكتمل",
        "in_progress": "قيد التنفيذ",
        "new": "جديد",
        "paused": "متوقف مؤقتًا",
        "cancelled": "ملغى",
    }
    clean = value.strip()
    return mapping.get(clean.lower(), clean)


def _split_pipe(value: str | None, limit: int = 3) -> list[str]:
    if not value:
        return []
    return [
        item.strip()
        for item in value.split("|")
        if item.strip()
    ][:limit]


def answer_from_sources(
    question: str,
    sources: list[SourceChunk],
) -> str:
    """Readable deterministic fallback when Gemini is unavailable.

    It intentionally summarizes structured source fields instead of dumping
    the complete retrieved chunks into the chat bubble.
    """
    if not sources:
        return (
            "لا توجد معلومات معتمدة كافية في ملف الطفل للإجابة على هذا السؤال."
        )

    intent = detect_intent(question)
    lines: list[str] = []

    for index, source in enumerate(sources, start=1):
        sections = _section_map(source.text)

        if source.source_type == "goal":
            title = sections.get("الهدف") or source.title.removeprefix("هدف · ").strip()
            status_value = _translate_status(
                sections.get("الحالة الحالية", "")
            )
            progress = sections.get("نسبة التقدم الحالية", "")
            latest = sections.get("آخر تحديث", "")
            detail = f"الهدف «{title}»"
            if progress:
                detail += f" بنسبة تقدم {progress}"
            if status_value:
                detail += f" وحالته {status_value}"
            if latest and latest != "لا توجد ملاحظة نصية":
                detail += f". آخر تحديث: {_short(latest, 110)}"
            lines.append(f"• {detail}. [{index}]")
            continue

        if source.source_type == "report":
            if intent == "follow_up":
                followups = _split_pipe(sections.get("إجراءات المتابعة"), 3)
                if followups:
                    for item in followups:
                        if "synthetic test document" not in item.lower():
                            lines.append(f"• {_short(item, 150)} [{index}]")
                    continue

            if intent == "needs":
                needs = _split_pipe(sections.get("الاحتياجات"), 3)
                if needs:
                    for item in needs:
                        lines.append(f"• {_short(item, 150)} [{index}]")
                    continue

            findings = _split_pipe(sections.get("أهم النتائج"), 3)
            summary = sections.get("الملخص")
            if findings:
                for item in findings:
                    lines.append(f"• {_short(item, 150)} [{index}]")
            elif summary:
                lines.append(f"• {_short(summary, 180)} [{index}]")
            else:
                lines.append(f"• {_short(source.text, 180)} [{index}]")
            continue

        if source.source_type == "voice":
            lines.append(
                f"• آخر ملاحظة صوتية معتمدة: {_short(source.text, 190)} [{index}]"
            )
            continue

        if source.source_type == "profile":
            if intent == "needs":
                values = _split_pipe(sections.get("الاحتياجات"), 3)
                support = _split_pipe(sections.get("متطلبات الدعم"), 2)
                for item in [*values, *support]:
                    lines.append(f"• {_short(item, 150)} [{index}]")
            else:
                needs = _split_pipe(sections.get("الاحتياجات"), 2)
                conditions = _split_pipe(sections.get("الحالات"), 2)
                parts: list[str] = []
                if conditions:
                    parts.append("الحالة: " + "، ".join(conditions))
                if needs:
                    parts.append("الاحتياجات: " + "، ".join(needs))
                if parts:
                    lines.append(f"• {'؛ '.join(parts)}. [{index}]")
            continue

    if not lines:
        lines = [
            f"• {_short(source.text, 170)} [{index}]"
            for index, source in enumerate(sources[:3], start=1)
        ]

    # Keep the fallback intentionally compact.
    lines = lines[:5]

    if intent == "goals":
        heading = "الأهداف الحالية:"
    elif intent == "follow_up":
        heading = "المتابعة القادمة:"
    elif intent == "voice":
        heading = "الملاحظات الصوتية المعتمدة:"
    elif intent == "reports":
        heading = "أهم ما ورد في التقرير:"
    elif intent == "needs":
        heading = "أهم الاحتياجات الحالية:"
    elif intent == "summary":
        heading = "الخلاصة:"
    else:
        heading = "حسب المعلومات المعتمدة:"

    return (
        heading
        + "\n"
        + "\n".join(lines)
        + "\n\nهذا مساعد تنسيقي يعتمد على بيانات الملف ولا يقدّم تشخيصًا طبيًا أو يغيّر خطة علاجية."
    )

