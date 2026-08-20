from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.constants import CarePermission, UserRole

ALLOWED_PERMISSIONS = {permission.value for permission in CarePermission}


def normalize_permissions(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if cleaned in ALLOWED_PERMISSIONS and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)
    return output


class InvitationCreate(BaseModel):
    email: EmailStr
    target_role: UserRole
    role_label: str | None = Field(default=None, max_length=120)
    permissions: list[str] = Field(default_factory=list, max_length=20)
    access_days: int | None = Field(default=None, ge=1, le=3650)

    @field_validator("permissions")
    @classmethod
    def valid_permissions(cls, values: list[str]) -> list[str]:
        return normalize_permissions(values)


class InvitationPublic(BaseModel):
    id: str
    child_id: str
    child_name: str
    email: EmailStr
    target_role: str
    role_label: str | None
    permissions: list[str]
    status: str
    access_expires_at: datetime | None
    invitation_expires_at: datetime
    created_at: datetime


class MemberPublic(BaseModel):
    membership_id: str
    membership_kind: str
    user_id: str
    full_name: str
    email: EmailStr
    account_role: str
    role_label: str | None
    verification_status: str
    guardian_type: str | None = None
    permissions: list[str]
    access_status: str
    expires_at: datetime | None
    is_primary_guardian: bool = False


class CareTeamOverview(BaseModel):
    child_id: str
    members: list[MemberPublic]
    pending_invitations: list[InvitationPublic]


class MembershipUpdate(BaseModel):
    permissions: list[str] = Field(default_factory=list, max_length=20)
    access_days: int | None = Field(default=None, ge=1, le=3650)

    @field_validator("permissions")
    @classmethod
    def valid_permissions(cls, values: list[str]) -> list[str]:
        return normalize_permissions(values)


class AuditLogPublic(BaseModel):
    id: str
    actor_user_id: str
    action: str
    entity_type: str
    entity_id: str | None
    details: dict
    created_at: datetime
