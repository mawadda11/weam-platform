from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


FollowUpDisplayStatus = Literal["upcoming", "today", "overdue", "completed"]


class FollowUpCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    due_date: date | None = None
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if len(cleaned) < 2:
            raise ValueError("Title is too short")
        return cleaned

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None


class FollowUpUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    due_date: date | None = None
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        if len(cleaned) < 2:
            raise ValueError("Title is too short")
        return cleaned

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None


class FollowUpFromAnalysisCreate(BaseModel):
    action_index: int = Field(ge=0)
    due_date: date | None = None
    title: str | None = Field(default=None, max_length=180)
    note: str | None = Field(default=None, max_length=2000)


class FollowUpPublic(BaseModel):
    id: str
    child_id: str
    title: str
    note: str | None
    due_date: date | None
    status: str
    display_status: FollowUpDisplayStatus
    source_type: str
    source_id: str | None
    source_label: str | None
    created_by_user_id: str
    created_by_name: str
    completed_by_user_id: str | None
    completed_by_name: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FollowUpSuggestionPublic(BaseModel):
    analysis_id: str
    report_id: str
    report_title: str
    action_index: int
    action_text: str
    extracted_due_date: date | None
    already_added: bool


class NotificationPublic(BaseModel):
    event_key: str
    notification_type: str
    title: str
    body: str
    child_id: str | None
    entity_type: str | None
    entity_id: str | None
    occurred_at: datetime
    is_read: bool
    url: str


class NotificationReadRequest(BaseModel):
    event_keys: list[str] = Field(min_length=1, max_length=100)
