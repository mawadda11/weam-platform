from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_guardian
from app.core.constants import GuardianType, UserRole
from app.db.session import get_db
from app.models.child import CareProfile, Child, ChildIdentity, GuardianMembership
from app.models.user import User
from app.schemas.child import ChildCreate, ChildPublic, ChildUpdate

router = APIRouter(prefix="/children", tags=["children"])


def _serialize(child: Child, membership: GuardianMembership) -> ChildPublic:
    return ChildPublic(
        id=child.id,
        first_name=child.identity.first_name,
        preferred_name=child.identity.preferred_name,
        birth_date=child.identity.birth_date,
        gender=child.identity.gender,
        conditions=list(child.care_profile.conditions or []),
        needs=list(child.care_profile.needs or []),
        support_requirements=list(child.care_profile.support_requirements or []),
        services=list(child.care_profile.services or []),
        summary=child.care_profile.summary,
        guardian_type=membership.guardian_type,
        created_at=child.created_at,
        updated_at=child.updated_at,
    )


def _load_child_for_guardian(db: Session, child_id: str, user_id: str) -> tuple[Child, GuardianMembership]:
    membership = db.scalar(
        select(GuardianMembership).where(
            GuardianMembership.child_id == child_id,
            GuardianMembership.guardian_user_id == user_id,
        )
    )
    if not membership:
        # 404 avoids leaking whether another family's child exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child profile not found")

    child = db.scalar(
        select(Child)
        .options(joinedload(Child.identity), joinedload(Child.care_profile))
        .where(Child.id == child_id)
    )
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child profile not found")
    return child, membership


@router.post("", response_model=ChildPublic, status_code=status.HTTP_201_CREATED)
def create_child(
    payload: ChildCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_guardian),
) -> ChildPublic:
    child = Child(created_by_user_id=user.id)
    child.identity = ChildIdentity(
        first_name=payload.first_name.strip(),
        preferred_name=payload.preferred_name.strip() if payload.preferred_name else None,
        birth_date=payload.birth_date,
        gender=payload.gender.strip() if payload.gender else None,
    )
    child.care_profile = CareProfile(
        conditions=payload.conditions,
        needs=payload.needs,
        support_requirements=payload.support_requirements,
        services=payload.services,
        summary=payload.summary.strip() if payload.summary else None,
    )
    membership = GuardianMembership(
        child=child,
        guardian_user_id=user.id,
        guardian_type=GuardianType.PRIMARY.value,
    )
    db.add_all([child, membership])
    db.commit()

    loaded_child, loaded_membership = _load_child_for_guardian(db, child.id, user.id)
    return _serialize(loaded_child, loaded_membership)


@router.get("", response_model=list[ChildPublic])
def list_children(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ChildPublic]:
    # Care-provider child access will be introduced with the care-team permission feature.
    if user.role != UserRole.GUARDIAN.value:
        return []

    memberships = db.scalars(
        select(GuardianMembership)
        .where(GuardianMembership.guardian_user_id == user.id)
        .order_by(GuardianMembership.created_at.asc())
    ).all()
    if not memberships:
        return []

    child_ids = [membership.child_id for membership in memberships]
    children = db.scalars(
        select(Child)
        .options(joinedload(Child.identity), joinedload(Child.care_profile))
        .where(Child.id.in_(child_ids))
    ).unique().all()
    child_by_id = {child.id: child for child in children}
    return [
        _serialize(child_by_id[membership.child_id], membership)
        for membership in memberships
        if membership.child_id in child_by_id
    ]


@router.get("/{child_id}", response_model=ChildPublic)
def get_child(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_guardian),
) -> ChildPublic:
    child, membership = _load_child_for_guardian(db, child_id, user.id)
    return _serialize(child, membership)


@router.patch("/{child_id}", response_model=ChildPublic)
def update_child(
    child_id: str,
    payload: ChildUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_guardian),
) -> ChildPublic:
    child, membership = _load_child_for_guardian(db, child_id, user.id)
    if membership.guardian_type != GuardianType.PRIMARY.value and "manage_child" not in (
        membership.permissions or []
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission")

    values = payload.model_dump(exclude_unset=True)
    identity_fields = {"first_name", "preferred_name", "birth_date", "gender"}
    care_fields = {"conditions", "needs", "support_requirements", "services", "summary"}

    for field in identity_fields & values.keys():
        value = values[field]
        if isinstance(value, str):
            value = value.strip() or None
        setattr(child.identity, field, value)

    for field in care_fields & values.keys():
        value = values[field]
        if field == "summary" and isinstance(value, str):
            value = value.strip() or None
        setattr(child.care_profile, field, value)

    db.add(child)
    db.commit()
    loaded_child, loaded_membership = _load_child_for_guardian(db, child.id, user.id)
    return _serialize(loaded_child, loaded_membership)
