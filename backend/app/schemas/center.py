from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CenterSpecialistSummary(BaseModel):
    id: str
    full_name: str
    professional_title: str
    specialty: str
    bio: str | None

    model_config = {"from_attributes": True}


class CenterPublic(BaseModel):
    id: str
    name: str
    description: str
    city: str
    region: str | None
    address: str
    specialties: list[str]
    services: list[str]
    served_needs: list[str]
    min_age_years: int | None
    max_age_years: int | None
    offers_in_person: bool
    offers_remote: bool
    phone: str
    email: str | None
    working_hours: str
    price_range: str | None
    latitude: float | None
    longitude: float | None
    specialists: list[CenterSpecialistSummary] = Field(default_factory=list)
    is_favorite: bool
    source_type: str
    last_reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CenterFilterOptions(BaseModel):
    cities: list[str]
    specialties: list[str]
    services: list[str]
