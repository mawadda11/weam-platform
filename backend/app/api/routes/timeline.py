from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.constants import CarePermission
from app.db.session import get_db
from app.models.care_team import AccessAuditLog
from app.models.child import Child
from app.models.goal import Goal, GoalUpdate
from app.models.report import Report
from app.models.user import User
from app.schemas.timeline import TimelineEventPublic
from app.services.access import require_child_access

router = APIRouter(tags=["timeline"])

ALL_TYPES = {"profile", "team", "report", "goal"}
GOAL_STATUS_LABELS = {
    "new": "جديد",
    "in_progress": "قيد العمل",
    "completed": "مكتمل",
    "paused": "متوقف مؤقتًا",
}


def _actor_name(
    db: Session,
    user_id: str | None,
    cache: dict[str, str],
) -> str | None:
    if not user_id:
        return None
    if user_id in cache:
        return cache[user_id]
    user = db.get(User, user_id)
    name = user.full_name if user else "مستخدم وئام"
    cache[user_id] = name
    return name


def _selected_types(raw: str | None) -> set[str]:
    if not raw:
        return set(ALL_TYPES)
    selected = {
        value.strip()
        for value in raw.split(",")
        if value.strip() in ALL_TYPES
    }
    return selected or set(ALL_TYPES)


@router.get(
    "/children/{child_id}/timeline",
    response_model=list[TimelineEventPublic],
)
def child_timeline(
    child_id: str,
    types: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TimelineEventPublic]:
    grant = require_child_access(
        db,
        child_id,
        user,
        CarePermission.VIEW_TIMELINE.value,
    )
    selected = _selected_types(types)
    events: list[TimelineEventPublic] = []
    user_cache: dict[str, str] = {}

    child = db.get(Child, child_id)
    if child and "profile" in selected:
        events.append(
            TimelineEventPublic(
                id=f"profile:{child.id}",
                event_type="profile",
                title="تم إنشاء ملف الرعاية",
                description="بدأت رحلة الطفل في وئام من ملف موحد.",
                actor_user_id=child.created_by_user_id,
                actor_name=_actor_name(
                    db,
                    child.created_by_user_id,
                    user_cache,
                ),
                occurred_at=child.created_at,
                data={},
            )
        )

    if "team" in selected:
        team_actions = {
            "invitation_created": (
                "تم إرسال دعوة لفريق الرعاية",
                "تمت دعوة عضو جديد للانضمام إلى ملف الطفل.",
            ),
            "invitation_accepted": (
                "انضم عضو جديد لفريق الرعاية",
                "تم قبول الدعوة وتفعيل الوصول حسب الصلاحيات المحددة.",
            ),
            "invitation_declined": (
                "تم رفض دعوة فريق الرعاية",
                "لم يتم تفعيل الوصول لهذه الدعوة.",
            ),
            "permissions_updated": (
                "تم تحديث صلاحيات عضو",
                "تم تعديل صلاحيات أو مدة الوصول داخل فريق الرعاية.",
            ),
            "access_revoked": (
                "تم إلغاء وصول عضو",
                "أُلغي الوصول مع الاحتفاظ بالمساهمات السابقة.",
            ),
        }
        logs = db.scalars(
            select(AccessAuditLog)
            .where(AccessAuditLog.child_id == child_id)
            .order_by(AccessAuditLog.created_at.desc())
        ).all()
        for item in logs:
            labels = team_actions.get(item.action)
            if not labels:
                continue
            events.append(
                TimelineEventPublic(
                    id=f"team:{item.id}",
                    event_type="team",
                    title=labels[0],
                    description=labels[1],
                    actor_user_id=item.actor_user_id,
                    actor_name=_actor_name(
                        db,
                        item.actor_user_id,
                        user_cache,
                    ),
                    occurred_at=item.created_at,
                    data={"action": item.action},
                )
            )

    if "report" in selected and (
        grant.is_primary_guardian
        or grant.allows(CarePermission.VIEW_REPORTS.value)
    ):
        reports = db.scalars(
            select(Report)
            .where(Report.child_id == child_id)
            .order_by(Report.created_at.desc())
        ).all()
        visible_reports = {
            item.id: item
            for item in reports
            if grant.is_primary_guardian
            or item.visibility == "care_team"
            or user.id in (item.allowed_user_ids or [])
        }
        if visible_reports:
            report_actions = {
                "report_uploaded": "تم رفع تقرير جديد",
                "report_version_uploaded": "أضيفت نسخة جديدة للتقرير",
                "report_metadata_updated": "تم تحديث بيانات التقرير",
                "report_archived": "تمت أرشفة التقرير",
            }
            report_logs = db.scalars(
                select(AccessAuditLog)
                .where(
                    AccessAuditLog.child_id == child_id,
                    AccessAuditLog.entity_type == "report",
                )
                .order_by(AccessAuditLog.created_at.desc())
            ).all()
            for item in report_logs:
                if item.entity_id not in visible_reports:
                    continue
                title = report_actions.get(item.action)
                if not title:
                    continue
                report = visible_reports[item.entity_id]
                events.append(
                    TimelineEventPublic(
                        id=f"report:{item.id}",
                        event_type="report",
                        title=title,
                        description=report.title,
                        actor_user_id=item.actor_user_id,
                        actor_name=_actor_name(
                            db,
                            item.actor_user_id,
                            user_cache,
                        ),
                        occurred_at=item.created_at,
                        data={
                            "report_id": report.id,
                            "report_type": report.report_type,
                            "action": item.action,
                        },
                    )
                )

    if "goal" in selected and (
        grant.is_primary_guardian
        or grant.allows(CarePermission.VIEW_GOALS.value)
    ):
        goals = db.scalars(
            select(Goal)
            .where(Goal.child_id == child_id)
            .order_by(Goal.created_at.desc())
        ).all()
        goal_by_id = {goal.id: goal for goal in goals}

        for goal in goals:
            events.append(
                TimelineEventPublic(
                    id=f"goal-created:{goal.id}",
                    event_type="goal",
                    title=f"هدف جديد: {goal.title}",
                    description=goal.description,
                    actor_user_id=goal.created_by_user_id,
                    actor_name=_actor_name(
                        db,
                        goal.created_by_user_id,
                        user_cache,
                    ),
                    occurred_at=goal.created_at,
                    data={
                        "goal_id": goal.id,
                        "status": goal.status,
                        "progress_percent": 0,
                    },
                )
            )

        if goal_by_id:
            updates = db.scalars(
                select(GoalUpdate)
                .where(GoalUpdate.goal_id.in_(list(goal_by_id)))
                .order_by(GoalUpdate.created_at.desc())
            ).all()
            for item in updates:
                goal = goal_by_id.get(item.goal_id)
                if not goal:
                    continue
                status_label = GOAL_STATUS_LABELS.get(item.status, item.status)
                description = item.note or (
                    f"التقدم {item.progress_percent}% — الحالة {status_label}"
                )
                events.append(
                    TimelineEventPublic(
                        id=f"goal-update:{item.id}",
                        event_type="goal",
                        title=f"تحديث هدف: {goal.title}",
                        description=description,
                        actor_user_id=item.actor_user_id,
                        actor_name=_actor_name(
                            db,
                            item.actor_user_id,
                            user_cache,
                        ),
                        occurred_at=item.created_at,
                        data={
                            "goal_id": goal.id,
                            "status": item.status,
                            "progress_percent": item.progress_percent,
                        },
                    )
                )

    events.sort(key=lambda item: item.occurred_at, reverse=True)
    return events
