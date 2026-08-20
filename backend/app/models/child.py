from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AccessStatus, GuardianType
from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Child(Base):
    __tablename__ = "children"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    identity: Mapped["ChildIdentity"] = relationship(
        back_populates="child", cascade="all, delete-orphan", uselist=False
    )
    care_profile: Mapped["CareProfile"] = relationship(
        back_populates="child", cascade="all, delete-orphan", uselist=False
    )
    guardians: Mapped[list["GuardianMembership"]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )


class ChildIdentity(Base):
    """Identity data is intentionally separated from care data."""

    __tablename__ = "child_identities"

    child_id: Mapped[str] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), primary_key=True
    )
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)

    child: Mapped[Child] = relationship(back_populates="identity")


class CareProfile(Base):
    """Care data stays diagnosis-agnostic so Weam can support multiple needs."""

    __tablename__ = "care_profiles"

    child_id: Mapped[str] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), primary_key=True
    )
    conditions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    needs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    support_requirements: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    services: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    child: Mapped[Child] = relationship(back_populates="care_profile")


class GuardianMembership(Base):
    __tablename__ = "guardian_memberships"
    __table_args__ = (UniqueConstraint("child_id", "guardian_user_id", name="uq_child_guardian"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    child_id: Mapped[str] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guardian_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guardian_type: Mapped[str] = mapped_column(
        String(24), default=GuardianType.PRIMARY.value, nullable=False
    )
    role_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    permissions: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: ["manage_child", "manage_care_team", "manage_permissions"],
        nullable=False,
    )
    access_status: Mapped[str] = mapped_column(
        String(24), default=AccessStatus.ACTIVE.value, nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    child: Mapped[Child] = relationship(back_populates="guardians")
