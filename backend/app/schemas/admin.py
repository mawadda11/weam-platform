from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


VerificationValue = Literal["verified", "unverified", "rejected"]


class AdminSummaryPublic(BaseModel):
    users_total: int
    users_active: int
    pending_accounts: int
    centers_total: int
    centers_active: int
    pending_centers: int
    child_profiles_total: int


class AdminUserPublic(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    provider_specialty: str | None
    verification_status: str
    verification_note: str | None
    is_active: bool
    created_at: datetime


class AdminUserUpdate(BaseModel):
    verification_status: VerificationValue | None = None
    verification_note: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None


class AdminCenterPublic(BaseModel):
    id: str
    name: str
    city: str
    verification_status: str
    verification_note: str | None
    is_active: bool
    account_count: int
    account_email: str | None
    source_type: str
    source_urls: list[str]
    last_reviewed_at: datetime | None
    data_confidence: str | None
    listing_claimed: bool
    created_at: datetime
    updated_at: datetime


class AdminCenterUpdate(BaseModel):
    verification_status: VerificationValue | None = None
    verification_note: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None
    source_urls: list[str] | None = Field(default=None, max_length=10)
    mark_reviewed: bool = False


class AdminAuditPublic(BaseModel):
    id: str
    actor_user_id: str
    actor_name: str
    action: str
    entity_type: str
    entity_id: str | None
    details: dict
    created_at: datetime
