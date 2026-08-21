from __future__ import annotations

import calendar
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.constants import CarePermission, InvitationStatus
from app.models.care_team import AccessAuditLog, CareInvitation, CareTeamMembership
from app.models.chat import ChatMessage, Conversation, ConversationParticipant
from app.models.child import GuardianMembership
from app.models.follow_up import FollowUp, NotificationReceipt
from app.models.goal import Goal
from app.models.report import Report
from app.models.report_ai import ReportAIAnalysis
from app.models.user import User
from app.services.access import membership_is_active, resolve_child_access


RIYADH = ZoneInfo("Asia/Riyadh")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
NUMBER_WORDS = {
    "واحد": 1,
    "واحدة": 1,
    "احد": 1,
    "أحد": 1,
    "اثنين": 2,
    "اثنان": 2,
    "اثنتين": 2,
    "اثنتان": 2,
    "ثلاث": 3,
    "ثلاثة": 3,
    "اربع": 4,
    "أربع": 4,
    "اربعة": 4,
    "أربعة": 4,
    "خمس": 5,
    "خمسة": 5,
    "ست": 6,
    "ستة": 6,
    "سبع": 7,
    "سبعة": 7,
    "ثمان": 8,
    "ثمانية": 8,
    "تسع": 9,
    "تسعة": 9,
    "عشر": 10,
    "عشرة": 10,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def local_today() -> date:
    return datetime.now(RIYADH).date()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def follow_up_display_status(item: FollowUp, today: date | None = None) -> str:
    if item.status == "completed":
        return "completed"
    current = today or local_today()
    if item.due_date is None:
        return "upcoming"
    if item.due_date < current:
        return "overdue"
    if item.due_date == current:
        return "today"
    return "upcoming"


def _number_value(raw: str) -> int | None:
    clean = raw.strip().translate(ARABIC_DIGITS)
    if clean.isdigit():
        return int(clean)
    return NUMBER_WORDS.get(clean)


def _add_months(base: date, months: int) -> date:
    month_index = (base.month - 1) + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def extract_iso_date(text: str) -> date | None:
    normalized = text.translate(ARABIC_DIGITS)
    for raw in re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", normalized):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            continue
    return None


def resolve_follow_up_due_date(
    text: str,
    *,
    report_date: date | None,
) -> date | None:
    exact = extract_iso_date(text)
    if exact:
        return exact

    if report_date is None:
        return None

    normalized = " ".join(text.translate(ARABIC_DIGITS).split())
    number_token = (
        r"(\d+|واحد|واحدة|احد|أحد|اثنين|اثنان|اثنتين|اثنتان|"
        r"ثلاث|ثلاثة|اربع|أربع|اربعة|أربعة|خمس|خمسة|ست|ستة|"
        r"سبع|سبعة|ثمان|ثمانية|تسع|تسعة|عشر|عشرة)"
    )

    arabic_pattern = re.search(
        rf"(?:بعد|خلال)\s+{number_token}\s*"
        r"(يوم|أيام|ايام|أسبوع|اسبوع|أسابيع|اسابيع|شهر|أشهر|اشهر|شهور)",
        normalized,
        flags=re.IGNORECASE,
    )
    if arabic_pattern:
        amount = _number_value(arabic_pattern.group(1))
        unit = arabic_pattern.group(2)
        if amount:
            if unit in {"يوم", "أيام", "ايام"}:
                return report_date + timedelta(days=amount)
            if unit in {"أسبوع", "اسبوع", "أسابيع", "اسابيع"}:
                return report_date + timedelta(weeks=amount)
            return _add_months(report_date, amount)

    english_pattern = re.search(
        r"(?:after|within)\s+(\d+)\s*(day|days|week|weeks|month|months)",
        normalized,
        flags=re.IGNORECASE,
    )
    if english_pattern:
        amount = int(english_pattern.group(1))
        unit = english_pattern.group(2).lower()
        if unit.startswith("day"):
            return report_date + timedelta(days=amount)
        if unit.startswith("week"):
            return report_date + timedelta(weeks=amount)
        return _add_months(report_date, amount)

    return None


def can_manage_follow_ups(grant) -> bool:
    return grant.is_primary_guardian or grant.allows(CarePermission.MANAGE_GOALS.value)


def can_view_follow_ups(grant) -> bool:
    return grant.is_primary_guardian or grant.allows(CarePermission.VIEW_TIMELINE.value)


def follow_up_source_id(report_id: str, action_text: str) -> str:
    normalized = " ".join(action_text.strip().lower().split())
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:20]
    return f"{report_id}:{digest}"


def sync_analysis_followups(
    db: Session,
    *,
    analysis: ReportAIAnalysis,
    report: Report,
    created_by_user_id: str,
) -> int:
    if (
        analysis.analysis_status != "completed"
        or analysis.review_status != "approved"
    ):
        return 0

    actions = (analysis.result_json or {}).get("follow_up_actions") or []
    if not isinstance(actions, list):
        return 0

    created = 0
    for action in actions:
        if not isinstance(action, str) or not action.strip():
            continue

        clean_action = " ".join(action.strip().split())
        source_id = follow_up_source_id(report.id, clean_action)
        existing = db.scalar(
            select(FollowUp.id).where(
                FollowUp.child_id == report.child_id,
                FollowUp.source_type == "report_ai",
                or_(
                    FollowUp.source_id == source_id,
                    FollowUp.note == clean_action,
                ),
            )
        )
        if existing:
            continue

        item = FollowUp(
            child_id=report.child_id,
            title=clean_action[:177] + ("..." if len(clean_action) > 177 else ""),
            note=clean_action,
            due_date=resolve_follow_up_due_date(
                clean_action,
                report_date=report.report_date,
            ),
            status="open",
            source_type="report_ai",
            source_id=source_id,
            source_label=f"تقرير معتمد · {report.title}",
            created_by_user_id=created_by_user_id,
        )
        db.add(item)
        created += 1

    return created


def sync_approved_followups_for_child(
    db: Session,
    *,
    child_id: str,
    created_by_user_id: str,
) -> int:
    analyses = db.scalars(
        select(ReportAIAnalysis)
        .where(
            ReportAIAnalysis.child_id == child_id,
            ReportAIAnalysis.analysis_status == "completed",
            ReportAIAnalysis.review_status == "approved",
        )
        .order_by(
            ReportAIAnalysis.reviewed_at.desc().nullslast(),
            ReportAIAnalysis.created_at.desc(),
        )
    ).all()

    seen_reports: set[str] = set()
    created = 0
    for analysis in analyses:
        if analysis.report_id in seen_reports:
            continue
        seen_reports.add(analysis.report_id)
        report = db.get(Report, analysis.report_id)
        if not report or report.is_archived:
            continue
        created += sync_analysis_followups(
            db,
            analysis=analysis,
            report=report,
            created_by_user_id=created_by_user_id,
        )
    return created


@dataclass(frozen=True)
class NotificationEvent:
    event_key: str
    notification_type: str
    title: str
    body: str
    child_id: str | None
    entity_type: str | None
    entity_id: str | None
    occurred_at: datetime
    url: str


def _child_ids_for_user(db: Session, user: User) -> set[str]:
    result: set[str] = set()

    guardians = db.scalars(
        select(GuardianMembership).where(
            GuardianMembership.guardian_user_id == user.id
        )
    ).all()
    for item in guardians:
        if membership_is_active(item.access_status, item.expires_at):
            result.add(item.child_id)

    providers = db.scalars(
        select(CareTeamMembership).where(
            CareTeamMembership.user_id == user.id
        )
    ).all()
    for item in providers:
        if membership_is_active(item.access_status, item.expires_at):
            result.add(item.child_id)

    return result


def _report_visible(report: Report, user: User, grant) -> bool:
    if grant.is_primary_guardian or report.visibility == "care_team":
        return True
    return user.id in (report.allowed_user_ids or [])


def collect_notification_events(
    db: Session,
    *,
    user: User,
    limit: int = 80,
) -> list[NotificationEvent]:
    events: list[NotificationEvent] = []
    cutoff = utcnow() - timedelta(days=60)
    today = local_today()

    invitations = db.scalars(
        select(CareInvitation)
        .where(
            CareInvitation.email == user.email.lower(),
            CareInvitation.status == InvitationStatus.PENDING.value,
            CareInvitation.invitation_expires_at > utcnow(),
        )
        .order_by(CareInvitation.created_at.desc())
    ).all()
    for invitation in invitations:
        events.append(
            NotificationEvent(
                event_key=f"invitation:{invitation.id}",
                notification_type="invitation",
                title="دعوة جديدة لفريق الرعاية",
                body="لديك دعوة جديدة للانضمام إلى ملف طفل في وئام.",
                child_id=invitation.child_id,
                entity_type="care_invitation",
                entity_id=invitation.id,
                occurred_at=invitation.created_at,
                url="/invitations",
            )
        )

    child_ids = _child_ids_for_user(db, user)
    for child_id in child_ids:
        grant = resolve_child_access(db, child_id, user)
        if not grant:
            continue

        if grant.is_primary_guardian or grant.allows(CarePermission.VIEW_REPORTS.value):
            logs = db.scalars(
                select(AccessAuditLog)
                .where(
                    AccessAuditLog.child_id == child_id,
                    AccessAuditLog.action.in_(
                        ["report_uploaded", "report_version_uploaded"]
                    ),
                    AccessAuditLog.created_at >= cutoff,
                )
                .order_by(AccessAuditLog.created_at.desc())
                .limit(20)
            ).all()
            for log in logs:
                if log.actor_user_id == user.id or not log.entity_id:
                    continue
                report = db.get(Report, log.entity_id)
                if not report or not _report_visible(report, user, grant):
                    continue
                events.append(
                    NotificationEvent(
                        event_key=f"audit:{log.id}",
                        notification_type="report",
                        title=(
                            "نسخة جديدة من تقرير"
                            if log.action == "report_version_uploaded"
                            else "تقرير جديد"
                        ),
                        body=report.title,
                        child_id=child_id,
                        entity_type="report",
                        entity_id=report.id,
                        occurred_at=log.created_at,
                        url=f"/children/{child_id}/reports",
                    )
                )

        if grant.is_primary_guardian or grant.allows(CarePermission.VIEW_GOALS.value):
            goal_logs = db.scalars(
                select(AccessAuditLog)
                .where(
                    AccessAuditLog.child_id == child_id,
                    AccessAuditLog.action.in_(
                        [
                            "goal_created",
                            "goal_progress_updated",
                            "goal_metadata_updated",
                        ]
                    ),
                    AccessAuditLog.created_at >= cutoff,
                )
                .order_by(AccessAuditLog.created_at.desc())
                .limit(20)
            ).all()
            for log in goal_logs:
                if log.actor_user_id == user.id or not log.entity_id:
                    continue
                goal = db.get(Goal, log.entity_id)
                if not goal:
                    continue
                events.append(
                    NotificationEvent(
                        event_key=f"audit:{log.id}",
                        notification_type="goal",
                        title=(
                            "تحديث على هدف"
                            if log.action != "goal_created"
                            else "هدف جديد"
                        ),
                        body=goal.title,
                        child_id=child_id,
                        entity_type="goal",
                        entity_id=goal.id,
                        occurred_at=log.created_at,
                        url=f"/children/{child_id}/goals",
                    )
                )

            goals = db.scalars(
                select(Goal).where(
                    Goal.child_id == child_id,
                    Goal.target_date.is_not(None),
                    Goal.status != "completed",
                )
            ).all()
            for goal in goals:
                if not goal.target_date:
                    continue
                days = (goal.target_date - today).days
                if days > 3:
                    continue
                if days < 0:
                    phase = "overdue"
                    title = "هدف تجاوز موعده"
                elif days == 0:
                    phase = "today"
                    title = "موعد هدف اليوم"
                else:
                    phase = "upcoming"
                    title = "موعد هدف قريب"

                events.append(
                    NotificationEvent(
                        event_key=f"goal-due:{goal.id}:{goal.target_date.isoformat()}:{phase}",
                        notification_type="goal_deadline",
                        title=title,
                        body=goal.title,
                        child_id=child_id,
                        entity_type="goal",
                        entity_id=goal.id,
                        occurred_at=datetime.combine(
                            goal.target_date,
                            datetime.min.time(),
                            tzinfo=RIYADH,
                        ).astimezone(timezone.utc),
                        url=f"/children/{child_id}/goals",
                    )
                )

        if can_view_follow_ups(grant):
            followups = db.scalars(
                select(FollowUp).where(
                    FollowUp.child_id == child_id,
                    FollowUp.status == "open",
                )
            ).all()
            for item in followups:
                if item.due_date is None:
                    continue
                days = (item.due_date - today).days
                if days > 3:
                    continue
                display = follow_up_display_status(item, today)
                if display == "overdue":
                    title = "متابعة متأخرة"
                elif display == "today":
                    title = "متابعة اليوم"
                else:
                    title = "متابعة قريبة"
                events.append(
                    NotificationEvent(
                        event_key=f"followup:{item.id}:{item.due_date.isoformat()}:{display}",
                        notification_type="follow_up",
                        title=title,
                        body=item.title,
                        child_id=child_id,
                        entity_type="follow_up",
                        entity_id=item.id,
                        occurred_at=datetime.combine(
                            item.due_date,
                            datetime.min.time(),
                            tzinfo=RIYADH,
                        ).astimezone(timezone.utc),
                        url=f"/children/{child_id}/follow-ups",
                    )
                )

        if grant.is_primary_guardian or grant.allows(CarePermission.MESSAGE_TEAM.value):
            conversation_ids = db.scalars(
                select(ConversationParticipant.conversation_id).where(
                    ConversationParticipant.user_id == user.id
                )
            ).all()
            if conversation_ids:
                conversations = db.scalars(
                    select(Conversation).where(
                        Conversation.id.in_(conversation_ids),
                        Conversation.child_id == child_id,
                    )
                ).all()
                by_id = {item.id: item for item in conversations}
                if by_id:
                    messages = db.scalars(
                        select(ChatMessage)
                        .where(
                            ChatMessage.conversation_id.in_(list(by_id)),
                            ChatMessage.sender_user_id != user.id,
                            ChatMessage.created_at >= cutoff,
                        )
                        .order_by(ChatMessage.created_at.desc())
                        .limit(25)
                    ).all()
                    for message in messages:
                        sender = db.get(User, message.sender_user_id)
                        sender_name = sender.full_name if sender else "عضو فريق الرعاية"
                        events.append(
                            NotificationEvent(
                                event_key=f"message:{message.id}",
                                notification_type="message",
                                title=f"رسالة جديدة من {sender_name}",
                                body=" ".join(message.body.split())[:140],
                                child_id=child_id,
                                entity_type="conversation",
                                entity_id=message.conversation_id,
                                occurred_at=message.created_at,
                                url=f"/children/{child_id}/communication",
                            )
                        )

    deduped: dict[str, NotificationEvent] = {}
    for event in events:
        deduped[event.event_key] = event
    ordered = sorted(
        deduped.values(),
        key=lambda item: _aware(item.occurred_at),
        reverse=True,
    )
    return ordered[:limit]


def read_event_keys(db: Session, *, user_id: str) -> set[str]:
    return set(
        db.scalars(
            select(NotificationReceipt.event_key).where(
                NotificationReceipt.user_id == user_id
            )
        ).all()
    )


def mark_event_keys_read(
    db: Session,
    *,
    user_id: str,
    event_keys: list[str],
) -> None:
    if not event_keys:
        return
    existing = read_event_keys(db, user_id=user_id)
    for key in event_keys:
        if key in existing:
            continue
        db.add(NotificationReceipt(user_id=user_id, event_key=key))
