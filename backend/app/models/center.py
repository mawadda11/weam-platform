from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Center(Base):
    __tablename__ = "centers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str] = mapped_column(String(300), nullable=False)

    specialties: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    services: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    served_needs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    min_age_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_age_years: Mapped[int | None] = mapped_column(Integer, nullable=True)

    offers_in_person: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    offers_remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    working_hours: Mapped[str] = mapped_column(String(240), nullable=False)
    price_range: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(
        String(24), default="unverified", nullable=False, index=True
    )
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Provenance of the listing's public-facing data — distinct from `verification_status`,
    # which reflects Weam's own admin verification workflow, not where the data came from.
    source_type: Mapped[str] = mapped_column(
        String(24), default="synthetic_demo", nullable=False, index=True
    )
    source_urls: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    listing_claimed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class CenterFavorite(Base):
    __tablename__ = "center_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "center_id", name="uq_center_favorite_user_center"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    center_id: Mapped[str] = mapped_column(
        ForeignKey("centers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
