from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import AccessStatus, GuardianType
from app.models.care_team import CareTeamMembership
from app.models.child import GuardianMembership
from app.models.user import User


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def membership_is_active(access_status: str, expires_at: datetime | None) -> bool:
    if access_status != AccessStatus.ACTIVE.value:
        return False
    expiry = _aware(expires_at)
    return expiry is None or expiry > utcnow()


@dataclass
class AccessGrant:
    membership_id: str
    access_role: str
    permissions: list[str]
    guardian_type: str | None = None
    is_primary_guardian: bool = False

    def allows(self, permission: str) -> bool:
        return self.is_primary_guardian or permission in self.permissions


def resolve_child_access(db: Session, child_id: str, user: User) -> AccessGrant | None:
    guardian = db.scalar(
        select(GuardianMembership).where(
            GuardianMembership.child_id == child_id,
            GuardianMembership.guardian_user_id == user.id,
        )
    )
    if guardian and membership_is_active(guardian.access_status, guardian.expires_at):
        is_primary = guardian.guardian_type == GuardianType.PRIMARY.value
        return AccessGrant(
            membership_id=guardian.id,
            access_role="guardian",
            permissions=list(guardian.permissions or []),
            guardian_type=guardian.guardian_type,
            is_primary_guardian=is_primary,
        )

    member = db.scalar(
        select(CareTeamMembership).where(
            CareTeamMembership.child_id == child_id,
            CareTeamMembership.user_id == user.id,
        )
    )
    if member and membership_is_active(member.access_status, member.expires_at):
        return AccessGrant(
            membership_id=member.id,
            access_role="care_provider",
            permissions=list(member.permissions or []),
        )
    return None


def require_child_access(
    db: Session,
    child_id: str,
    user: User,
    permission: str | None = None,
) -> AccessGrant:
    grant = resolve_child_access(db, child_id, user)
    if not grant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child profile not found")
    if permission and not grant.allows(permission):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission")
    return grant
