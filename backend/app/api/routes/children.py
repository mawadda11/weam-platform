from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_guardian
from app.core.constants import CarePermission, GuardianType, UserRole
from app.db.session import get_db
from app.models.care_team import CareTeamMembership
from app.models.child import CareProfile, Child, ChildIdentity, GuardianMembership
from app.models.user import User
from app.schemas.child import ChildCreate, ChildPublic, ChildUpdate
from app.services.access import AccessGrant, membership_is_active, require_child_access, resolve_child_access

router = APIRouter(prefix="/children", tags=["children"])


def _serialize(child: Child, grant: AccessGrant) -> ChildPublic:
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
        guardian_type=grant.guardian_type,
        access_role=grant.access_role,
        access_permissions=list(grant.permissions),
        created_at=child.created_at,
        updated_at=child.updated_at,
    )


def _load_child(db: Session, child_id: str) -> Child:
    child = db.scalar(
        select(Child)
        .options(joinedload(Child.identity), joinedload(Child.care_profile))
        .where(Child.id == child_id)
    )
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child profile not found")
    return child


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
        role_label="ولي أمر رئيسي",
        permissions=[permission.value for permission in CarePermission],
    )
    db.add_all([child, membership])
    db.commit()

    grant = resolve_child_access(db, child.id, user)
    assert grant is not None
    return _serialize(_load_child(db, child.id), grant)


@router.get("", response_model=list[ChildPublic])
def list_children(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ChildPublic]:
    child_ids: list[str] = []
    if user.role == UserRole.GUARDIAN.value:
        memberships = db.scalars(
            select(GuardianMembership)
            .where(GuardianMembership.guardian_user_id == user.id)
            .order_by(GuardianMembership.created_at.asc())
        ).all()
        child_ids = [m.child_id for m in memberships if membership_is_active(m.access_status, m.expires_at)]
    elif user.role == UserRole.CARE_PROVIDER.value:
        memberships = db.scalars(
            select(CareTeamMembership)
            .where(CareTeamMembership.user_id == user.id)
            .order_by(CareTeamMembership.created_at.asc())
        ).all()
        child_ids = [m.child_id for m in memberships if membership_is_active(m.access_status, m.expires_at)]
    else:
        return []

    if not child_ids:
        return []

    children = db.scalars(
        select(Child)
        .options(joinedload(Child.identity), joinedload(Child.care_profile))
        .where(Child.id.in_(child_ids))
    ).unique().all()
    child_by_id = {child.id: child for child in children}
    output: list[ChildPublic] = []
    for child_id in child_ids:
        child = child_by_id.get(child_id)
        grant = resolve_child_access(db, child_id, user)
        if child and grant and grant.allows(CarePermission.VIEW_PROFILE.value):
            output.append(_serialize(child, grant))
    return output


@router.get("/{child_id}", response_model=ChildPublic)
def get_child(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChildPublic:
    grant = require_child_access(db, child_id, user, CarePermission.VIEW_PROFILE.value)
    return _serialize(_load_child(db, child_id), grant)


@router.patch("/{child_id}", response_model=ChildPublic)
def update_child(
    child_id: str,
    payload: ChildUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChildPublic:
    grant = require_child_access(db, child_id, user, CarePermission.MANAGE_CHILD.value)
    if grant.access_role != "guardian":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Guardian account required")

    child = _load_child(db, child_id)
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
    updated_grant = require_child_access(db, child_id, user, CarePermission.VIEW_PROFILE.value)
    return _serialize(_load_child(db, child.id), updated_grant)
