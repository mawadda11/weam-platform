from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ReportVisibility = Literal["care_team", "restricted"]


def normalize_user_ids(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


class ReportVersionPublic(BaseModel):
    id: str
    version_number: int
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    notes: str | None
    uploaded_by_user_id: str
    uploaded_by_name: str
    created_at: datetime


class ReportPublic(BaseModel):
    id: str
    child_id: str
    title: str
    report_type: str
    report_date: date | None
    source_label: str | None
    visibility: ReportVisibility
    allowed_user_ids: list[str]
    created_by_user_id: str
    created_by_name: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    versions: list[ReportVersionPublic]


class ReportMetadataUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=220)
    report_type: str | None = Field(default=None, min_length=1, max_length=80)
    report_date: date | None = None
    source_label: str | None = Field(default=None, max_length=180)
    visibility: ReportVisibility | None = None
    allowed_user_ids: list[str] | None = Field(default=None, max_length=100)

    @field_validator("title", "report_type")
    @classmethod
    def trim_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("value cannot be blank")
        return cleaned

    @field_validator("source_label")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().split()) or None

    @field_validator("allowed_user_ids")
    @classmethod
    def clean_allowed_users(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else normalize_user_ids(value)
