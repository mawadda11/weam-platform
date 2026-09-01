from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.constants import UserRole, VerificationStatus
from app.db.session import get_db
from app.models.admin import AdminAuditLog
from app.models.center import Center
from app.models.center_account import CenterAccountMembership
from app.models.child import Child
from app.models.user import User
from app.schemas.admin import (
    AdminAuditPublic,
    AdminCenterPublic,
    AdminCenterUpdate,
    AdminSummaryPublic,
    AdminUserPublic,
    AdminUserUpdate,
)

router = APIRouter(prefix="/admin", tags=["administration"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _audit(
    db: Session,
    *,
    actor: User,
    action: str,
    entity_type: str,
    entity_id: str | None,
    details: dict,
) -> None:
    db.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )


def _serialize_user(item: User) -> AdminUserPublic:
    return AdminUserPublic(
        id=item.id,
        email=item.email,
        full_name=item.full_name,
        role=item.role,
        provider_specialty=item.provider_specialty,
        verification_status=item.verification_status,
        verification_note=item.verification_note,
        is_active=item.is_active,
        created_at=item.created_at,
    )


def _serialize_center(db: Session, item: Center) -> AdminCenterPublic:
    memberships = db.scalars(
        select(CenterAccountMembership).where(
            CenterAccountMembership.center_id == item.id,
            CenterAccountMembership.is_active.is_(True),
        )
    ).all()
    first_user = db.get(User, memberships[0].user_id) if memberships else None
    return AdminCenterPublic(
        id=item.id,
        name=item.name,
        city=item.city,
        verification_status=item.verification_status,
        verification_note=item.verification_note,
        is_active=item.is_active,
        account_count=len(memberships),
        account_email=first_user.email if first_user else None,
        source_type=item.source_type,
        source_urls=list(item.source_urls or []),
        last_reviewed_at=item.last_reviewed_at,
        data_confidence=item.data_confidence,
        listing_claimed=item.listing_claimed,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/summary", response_model=AdminSummaryPublic)
def admin_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> AdminSummaryPublic:
    return AdminSummaryPublic(
        users_total=int(db.scalar(select(func.count(User.id))) or 0),
        users_active=int(db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0),
        pending_accounts=int(
            db.scalar(
                select(func.count(User.id)).where(
                    User.role.in_([UserRole.CARE_PROVIDER.value, UserRole.CENTER.value]),
                    User.verification_status == VerificationStatus.UNVERIFIED.value,
                )
            )
            or 0
        ),
        centers_total=int(db.scalar(select(func.count(Center.id))) or 0),
        centers_active=int(db.scalar(select(func.count(Center.id)).where(Center.is_active.is_(True))) or 0),
        pending_centers=int(
            db.scalar(
                select(func.count(Center.id)).where(
                    Center.verification_status == VerificationStatus.UNVERIFIED.value
                )
            )
            or 0
        ),
        child_profiles_total=int(db.scalar(select(func.count(Child.id))) or 0),
    )


@router.get("/users", response_model=list[AdminUserPublic])
def list_admin_users(
    q: str | None = Query(default=None, max_length=120),
    role: str | None = Query(default=None, max_length=32),
    verification_status: str | None = Query(default=None, max_length=24),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AdminUserPublic]:
    statement = select(User).order_by(User.created_at.desc()).limit(300)
    if q and q.strip():
        query = f"%{q.strip()}%"
        statement = statement.where(or_(User.full_name.ilike(query), User.email.ilike(query)))
    if role:
        statement = statement.where(User.role == role)
    if verification_status:
        statement = statement.where(User.verification_status == verification_status)
    return [_serialize_user(item) for item in db.scalars(statement).all()]


@router.patch("/users/{user_id}", response_model=AdminUserPublic)
def update_admin_user(
    user_id: str,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AdminUserPublic:
    item = db.get(User, user_id)
    if not item:
        raise HTTPException(status_code=404, detail="User not found")
    values = payload.model_dump(exclude_unset=True)
    if item.id == admin.id and values.get("is_active") is False:
        raise HTTPException(status_code=400, detail="You cannot disable your own admin account")
    before = {
        "verification_status": item.verification_status,
        "is_active": item.is_active,
    }
    for field in {"verification_note", "is_active"} & values.keys():
        setattr(item, field, values[field])
    if "verification_status" in values and values["verification_status"] is not None:
        item.verification_status = values["verification_status"]
        if item.verification_status == VerificationStatus.VERIFIED.value:
            item.verified_at = utcnow()
            item.verified_by_user_id = admin.id
        else:
            item.verified_at = None
            item.verified_by_user_id = None
    _audit(
        db,
        actor=admin,
        action="user_reviewed",
        entity_type="user",
        entity_id=item.id,
        details={"before": before, "after": values},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_user(item)


@router.get("/centers", response_model=list[AdminCenterPublic])
def list_admin_centers(
    q: str | None = Query(default=None, max_length=120),
    verification_status: str | None = Query(default=None, max_length=24),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AdminCenterPublic]:
    statement = select(Center).order_by(Center.created_at.desc()).limit(300)
    if q and q.strip():
        query = f"%{q.strip()}%"
        statement = statement.where(or_(Center.name.ilike(query), Center.city.ilike(query)))
    if verification_status:
        statement = statement.where(Center.verification_status == verification_status)
    return [_serialize_center(db, item) for item in db.scalars(statement).all()]


@router.patch("/centers/{center_id}", response_model=AdminCenterPublic)
def update_admin_center(
    center_id: str,
    payload: AdminCenterUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AdminCenterPublic:
    item = db.get(Center, center_id)
    if not item:
        raise HTTPException(status_code=404, detail="Center not found")
    values = payload.model_dump(exclude_unset=True)
    before = {
        "verification_status": item.verification_status,
        "is_active": item.is_active,
        "last_reviewed_at": item.last_reviewed_at.isoformat() if item.last_reviewed_at else None,
    }
    for field in {"verification_note", "is_active"} & values.keys():
        setattr(item, field, values[field])
    if "verification_status" in values and values["verification_status"] is not None:
        item.verification_status = values["verification_status"]
        if item.verification_status == VerificationStatus.VERIFIED.value:
            item.verified_at = utcnow()
            item.verified_by_user_id = admin.id
        else:
            item.verified_at = None
            item.verified_by_user_id = None

    # Public-source review is deliberately separate from formal verification above:
    # reviewing/refreshing where the data came from does not, by itself, mean Weam
    # has verified the center.
    if values.get("source_urls") is not None:
        item.source_urls = values["source_urls"]
    if payload.mark_reviewed:
        item.last_reviewed_at = utcnow()

    _audit(
        db,
        actor=admin,
        action="center_reviewed",
        entity_type="center",
        entity_id=item.id,
        details={"before": before, "after": values},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_center(db, item)


@router.get("/audit", response_model=list[AdminAuditPublic])
def admin_audit_log(
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AdminAuditPublic]:
    rows = db.scalars(
        select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(limit)
    ).all()
    output: list[AdminAuditPublic] = []
    for item in rows:
        actor = db.get(User, item.actor_user_id)
        output.append(
            AdminAuditPublic(
                id=item.id,
                actor_user_id=item.actor_user_id,
                actor_name=actor.full_name if actor else "إدارة وئام",
                action=item.action,
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                details=dict(item.details or {}),
                created_at=item.created_at,
            )
        )
    return output
