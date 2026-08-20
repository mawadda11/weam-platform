from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.constants import CarePermission, GoalStatus
from app.db.session import get_db
from app.models.care_team import AccessAuditLog, CareTeamMembership
from app.models.child import GuardianMembership
from app.models.goal import Goal, GoalUpdate
from app.models.user import User
from app.schemas.goal import (
    GoalCreate,
    GoalMetadataUpdate,
    GoalProgressCreate,
    GoalPublic,
    GoalUpdatePublic,
)
from app.services.access import membership_is_active, require_child_access

router = APIRouter(tags=["goals"])


def _audit(
    db: Session,
    *,
    child_id: str,
    actor_user_id: str,
    action: str,
    goal_id: str,
    details: dict | None = None,
) -> None:
    db.add(
        AccessAuditLog(
            child_id=child_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type="goal",
            entity_id=goal_id,
            details=details or {},
        )
    )


def _goal_query(goal_id: str):
    return (
        select(Goal)
        .options(selectinload(Goal.updates))
        .execution_options(populate_existing=True)
        .where(Goal.id == goal_id)
    )


def _goal_or_404(db: Session, goal_id: str) -> Goal:
    goal = db.scalar(_goal_query(goal_id))
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )
    return goal


def _active_team_user_ids(db: Session, child_id: str) -> set[str]:
    result: set[str] = set()

    guardians = db.scalars(
        select(GuardianMembership).where(
            GuardianMembership.child_id == child_id
        )
    ).all()
    for membership in guardians:
        if membership_is_active(
            membership.access_status,
            membership.expires_at,
        ):
            result.add(membership.guardian_user_id)

    providers = db.scalars(
        select(CareTeamMembership).where(
            CareTeamMembership.child_id == child_id
        )
    ).all()
    for membership in providers:
        if membership_is_active(
            membership.access_status,
            membership.expires_at,
        ):
            result.add(membership.user_id)

    return result


def _validate_assignee(
    db: Session,
    child_id: str,
    user_id: str | None,
) -> None:
    if not user_id:
        return
    if user_id not in _active_team_user_ids(db, child_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Goal owner must be an active member of the care team",
        )


def _serialize_update(db: Session, item: GoalUpdate) -> GoalUpdatePublic:
    actor = db.get(User, item.actor_user_id)
    return GoalUpdatePublic(
        id=item.id,
        actor_user_id=item.actor_user_id,
        actor_name=actor.full_name if actor else "مستخدم وئام",
        note=item.note,
        progress_percent=item.progress_percent,
        status=item.status,
        created_at=item.created_at,
    )


def _serialize_goal(db: Session, goal: Goal) -> GoalPublic:
    creator = db.get(User, goal.created_by_user_id)
    assignee = db.get(User, goal.assigned_to_user_id) if goal.assigned_to_user_id else None
    updates = sorted(
        list(goal.updates or []),
        key=lambda item: item.created_at,
        reverse=True,
    )
    return GoalPublic(
        id=goal.id,
        child_id=goal.child_id,
        title=goal.title,
        description=goal.description,
        category=goal.category,
        status=goal.status,
        progress_percent=goal.progress_percent,
        start_date=goal.start_date,
        target_date=goal.target_date,
        assigned_to_user_id=goal.assigned_to_user_id,
        assigned_to_name=assignee.full_name if assignee else None,
        created_by_user_id=goal.created_by_user_id,
        created_by_name=creator.full_name if creator else "مستخدم وئام",
        created_at=goal.created_at,
        updated_at=goal.updated_at,
        updates=[_serialize_update(db, item) for item in updates],
    )


@router.get("/children/{child_id}/goals", response_model=list[GoalPublic])
def list_goals(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[GoalPublic]:
    require_child_access(
        db,
        child_id,
        user,
        CarePermission.VIEW_GOALS.value,
    )
    goals = db.scalars(
        select(Goal)
        .options(selectinload(Goal.updates))
        .where(Goal.child_id == child_id)
        .order_by(Goal.created_at.desc())
    ).unique().all()
    return [_serialize_goal(db, goal) for goal in goals]


@router.post(
    "/children/{child_id}/goals",
    response_model=GoalPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_goal(
    child_id: str,
    payload: GoalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GoalPublic:
    require_child_access(
        db,
        child_id,
        user,
        CarePermission.MANAGE_GOALS.value,
    )
    _validate_assignee(db, child_id, payload.assigned_to_user_id)

    title = " ".join(payload.title.strip().split())
    if not title:
        raise HTTPException(status_code=422, detail="Goal title is required")

    goal = Goal(
        child_id=child_id,
        title=title,
        description=payload.description.strip() if payload.description else None,
        category=" ".join(payload.category.strip().split()) if payload.category else None,
        status=GoalStatus.NEW.value,
        progress_percent=0,
        start_date=payload.start_date,
        target_date=payload.target_date,
        assigned_to_user_id=payload.assigned_to_user_id,
        created_by_user_id=user.id,
    )
    db.add(goal)
    db.flush()
    _audit(
        db,
        child_id=child_id,
        actor_user_id=user.id,
        action="goal_created",
        goal_id=goal.id,
        details={
            "title": goal.title,
            "assigned_to_user_id": goal.assigned_to_user_id,
        },
    )
    db.commit()

    created = _goal_or_404(db, goal.id)
    return _serialize_goal(db, created)


@router.get("/goals/{goal_id}", response_model=GoalPublic)
def get_goal(
    goal_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GoalPublic:
    goal = _goal_or_404(db, goal_id)
    require_child_access(
        db,
        goal.child_id,
        user,
        CarePermission.VIEW_GOALS.value,
    )
    return _serialize_goal(db, goal)


@router.patch("/goals/{goal_id}", response_model=GoalPublic)
def update_goal_metadata(
    goal_id: str,
    payload: GoalMetadataUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GoalPublic:
    goal = _goal_or_404(db, goal_id)
    require_child_access(
        db,
        goal.child_id,
        user,
        CarePermission.MANAGE_GOALS.value,
    )

    values = payload.model_dump(exclude_unset=True)
    next_start = values.get("start_date", goal.start_date)
    next_target = values.get("target_date", goal.target_date)
    if next_start and next_target and next_target < next_start:
        raise HTTPException(
            status_code=422,
            detail="target_date cannot be before start_date",
        )

    if "assigned_to_user_id" in values:
        _validate_assignee(
            db,
            goal.child_id,
            values["assigned_to_user_id"],
        )

    for field in {
        "title",
        "description",
        "category",
        "start_date",
        "target_date",
        "assigned_to_user_id",
    } & values.keys():
        value = values[field]
        if isinstance(value, str):
            value = " ".join(value.strip().split()) or None
        setattr(goal, field, value)

    if not goal.title:
        raise HTTPException(status_code=422, detail="Goal title is required")

    _audit(
        db,
        child_id=goal.child_id,
        actor_user_id=user.id,
        action="goal_metadata_updated",
        goal_id=goal.id,
    )
    db.add(goal)
    db.commit()

    updated = _goal_or_404(db, goal.id)
    return _serialize_goal(db, updated)


@router.post(
    "/goals/{goal_id}/updates",
    response_model=GoalPublic,
    status_code=status.HTTP_201_CREATED,
)
def add_goal_progress(
    goal_id: str,
    payload: GoalProgressCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GoalPublic:
    goal = _goal_or_404(db, goal_id)
    require_child_access(
        db,
        goal.child_id,
        user,
        CarePermission.MANAGE_GOALS.value,
    )

    next_status = payload.status.value if payload.status else goal.status
    next_progress = (
        payload.progress_percent
        if payload.progress_percent is not None
        else goal.progress_percent
    )

    # A completed goal is always represented as 100% to avoid inconsistent
    # states such as "completed" with 15% progress.
    if next_status == GoalStatus.COMPLETED.value:
        next_progress = 100

    goal.status = next_status
    goal.progress_percent = next_progress
    note = payload.note.strip() if payload.note and payload.note.strip() else None

    update = GoalUpdate(
        goal_id=goal.id,
        actor_user_id=user.id,
        note=note,
        progress_percent=next_progress,
        status=next_status,
    )
    db.add(goal)
    db.add(update)
    db.flush()
    _audit(
        db,
        child_id=goal.child_id,
        actor_user_id=user.id,
        action="goal_progress_updated",
        goal_id=goal.id,
        details={
            "progress_percent": next_progress,
            "status": next_status,
        },
    )
    db.commit()

    updated = _goal_or_404(db, goal.id)
    return _serialize_goal(db, updated)
