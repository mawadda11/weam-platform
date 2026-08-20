from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.core.constants import GoalStatus


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=3000)
    category: str | None = Field(default=None, max_length=80)
    start_date: date | None = None
    target_date: date | None = None
    assigned_to_user_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.target_date and self.target_date < self.start_date:
            raise ValueError("target_date cannot be before start_date")
        return self


class GoalMetadataUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=3000)
    category: str | None = Field(default=None, max_length=80)
    start_date: date | None = None
    target_date: date | None = None
    assigned_to_user_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.target_date and self.target_date < self.start_date:
            raise ValueError("target_date cannot be before start_date")
        return self


class GoalProgressCreate(BaseModel):
    note: str | None = Field(default=None, max_length=3000)
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    status: GoalStatus | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not (self.note and self.note.strip()) and self.progress_percent is None and self.status is None:
            raise ValueError("At least one progress field is required")
        return self


class GoalUpdatePublic(BaseModel):
    id: str
    actor_user_id: str
    actor_name: str
    note: str | None
    progress_percent: int
    status: str
    created_at: datetime


class GoalPublic(BaseModel):
    id: str
    child_id: str
    title: str
    description: str | None
    category: str | None
    status: str
    progress_percent: int
    start_date: date | None
    target_date: date | None
    assigned_to_user_id: str | None
    assigned_to_name: str | None
    created_by_user_id: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    updates: list[GoalUpdatePublic]
