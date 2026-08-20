from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


def clean_tags(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


class ChildCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=32)
    conditions: list[str] = Field(default_factory=list, max_length=20)
    needs: list[str] = Field(default_factory=list, max_length=30)
    support_requirements: list[str] = Field(default_factory=list, max_length=30)
    services: list[str] = Field(default_factory=list, max_length=30)
    summary: str | None = Field(default=None, max_length=3000)

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("birth_date cannot be in the future")
        return value

    @field_validator("conditions", "needs", "support_requirements", "services")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return clean_tags(value)


class ChildUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=32)
    conditions: list[str] | None = Field(default=None, max_length=20)
    needs: list[str] | None = Field(default=None, max_length=30)
    support_requirements: list[str] | None = Field(default=None, max_length=30)
    services: list[str] | None = Field(default=None, max_length=30)
    summary: str | None = Field(default=None, max_length=3000)

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("birth_date cannot be in the future")
        return value

    @field_validator("conditions", "needs", "support_requirements", "services")
    @classmethod
    def normalize_optional_tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else clean_tags(value)


class ChildPublic(BaseModel):
    id: str
    first_name: str
    preferred_name: str | None
    birth_date: date | None
    gender: str | None
    conditions: list[str]
    needs: list[str]
    support_requirements: list[str]
    services: list[str]
    summary: str | None
    guardian_type: str
    created_at: datetime
    updated_at: datetime
