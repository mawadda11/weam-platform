"""Shared pool (guardians, specialists, demo centers) and helpers for the
four-child demo seed. See docs/SEED_DATA_ARCHITECTURE.md for the design.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers, UploadFile

from app.core.constants import GuardianType, UserRole, VerificationStatus
from app.models.care_team import AccessAuditLog
from app.models.center import Center
from app.models.follow_up import NotificationReceipt
from app.models.user import User
from app.services.access import AccessGrant
from app.services.security import hash_password
from app.services.storage import LocalReportStorage, LocalVoiceStorage, StoredFile

DEMO_BATCH = "weam-demo-2026"
DEMO_PASSWORD = "WeamDemo123!"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


@dataclass
class SeedContext:
    db: Session
    now: datetime
    guardian: User
    secondary_guardian: User
    specialists: dict[str, User]
    center_rep: User
    centers: dict[str, Center]
    report_storage: LocalReportStorage = field(default_factory=LocalReportStorage)
    voice_storage: LocalVoiceStorage = field(default_factory=LocalVoiceStorage)

    def guardian_grant(self) -> AccessGrant:
        return AccessGrant(
            membership_id="seed",
            access_role="guardian",
            permissions=[],
            guardian_type=GuardianType.PRIMARY.value,
            is_primary_guardian=True,
        )


def days_ago(now: datetime, n: int) -> datetime:
    return now - timedelta(days=n)


def days_from_now(now: datetime, n: int) -> datetime:
    return now + timedelta(days=n)


def date_days_ago(now: datetime, n: int) -> date:
    return days_ago(now, n).date()


def date_days_from_now(now: datetime, n: int) -> date:
    return days_from_now(now, n).date()


def _get_or_create_user(db: Session, *, email: str, full_name: str, role: str,
                         provider_specialty: str | None = None) -> User:
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        return existing
    user = User(
        email=email,
        full_name=full_name,
        password_hash=hash_password(DEMO_PASSWORD),
        role=role,
        provider_specialty=provider_specialty,
        verification_status=VerificationStatus.VERIFIED.value,
        auth_provider="password",
        demo_batch=DEMO_BATCH,
    )
    db.add(user)
    db.flush()
    return user


def _get_or_create_center(db: Session, *, name: str, city: str, description: str,
                           services: list[str], specialties: list[str], served_needs: list[str],
                           min_age_years: int | None, max_age_years: int | None) -> Center:
    existing = db.scalar(select(Center).where(Center.name == name, Center.city == city))
    if existing:
        return existing
    center = Center(
        name=name,
        description=description,
        city=city,
        region="منطقة الرياض" if city == "الرياض" else "منطقة مكة المكرمة",
        address="عنوان تجريبي وهمي لأغراض العرض",
        specialties=specialties,
        services=services,
        served_needs=served_needs,
        min_age_years=min_age_years,
        max_age_years=max_age_years,
        offers_in_person=True,
        offers_remote=False,
        phone="0500000000",
        email=None,
        working_hours="الأحد – الخميس، 9ص – 5م (بيانات تجريبية)",
        is_active=True,
        verification_status="verified",
        source_type="synthetic_demo",
        source_urls=[],
        data_confidence=None,
    )
    db.add(center)
    db.flush()
    return center


def build_pool(db: Session, *, now: datetime) -> SeedContext:
    guardian = _get_or_create_user(
        db, email="guardian@weam.demo", full_name="منى الشمري", role=UserRole.GUARDIAN.value,
    )
    secondary_guardian = _get_or_create_user(
        db, email="guardian2@weam.demo", full_name="فهد الشمري", role=UserRole.GUARDIAN.value,
    )

    specialists = {
        "slp": _get_or_create_user(
            db, email="slp@weam.demo", full_name="سارة العتيبي", role=UserRole.CARE_PROVIDER.value,
            provider_specialty="نطق وتخاطب",
        ),
        "pt": _get_or_create_user(
            db, email="pt@weam.demo", full_name="خالد الدوسري", role=UserRole.CARE_PROVIDER.value,
            provider_specialty="علاج طبيعي",
        ),
        "edu": _get_or_create_user(
            db, email="edu@weam.demo", full_name="منى الحربي", role=UserRole.CARE_PROVIDER.value,
            provider_specialty="تربية خاصة",
        ),
        "ot": _get_or_create_user(
            db, email="ot@weam.demo", full_name="هند القحطاني", role=UserRole.CARE_PROVIDER.value,
            provider_specialty="علاج وظيفي",
        ),
    }

    center_rep = _get_or_create_user(
        db, email="center@weam.demo", full_name="عبدالله المطيري", role=UserRole.CENTER.value,
    )

    centers = {
        "hearing": _get_or_create_center(
            db,
            name="مركز تجريبي للسمعيات والتخاطب",
            city="الرياض",
            description="مركز تجريبي (بيانات اصطناعية) لخدمات السمعيات والنطق والتخاطب.",
            services=["سمعيات", "نطق وتخاطب", "متابعة سمعية"],
            specialties=["ضعف سمع", "اضطرابات النطق واللغة"],
            served_needs=["دعم التواصل", "متابعة سمعية", "تنسيق المتابعات"],
            min_age_years=1,
            max_age_years=12,
        ),
        "mobility": _get_or_create_center(
            db,
            name="مركز تجريبي للتأهيل الحركي",
            city="الرياض",
            description="مركز تجريبي (بيانات اصطناعية) للعلاج الطبيعي والدعم الحركي.",
            services=["علاج طبيعي", "دعم حركي"],
            specialties=["إعاقة حركية", "ضعف توازن"],
            served_needs=["دعم حركي", "تنسيق المتابعات"],
            min_age_years=4,
            max_age_years=16,
        ),
        "education": _get_or_create_center(
            db,
            name="مركز تجريبي للدعم التعليمي",
            city="جدة",
            description="مركز تجريبي (بيانات اصطناعية) لخدمات الدعم التعليمي والتربية الخاصة.",
            services=["دعم تعليمي", "تربية خاصة"],
            specialties=["صعوبات تعلم", "تأخر أكاديمي"],
            served_needs=["دعم تعليمي", "روتين منظم"],
            min_age_years=5,
            max_age_years=14,
        ),
        "early_intervention": _get_or_create_center(
            db,
            name="مركز تجريبي للتدخل المبكر",
            city="جدة",
            description="مركز تجريبي (بيانات اصطناعية) لخدمات التدخل المبكر والعلاج الوظيفي.",
            services=["تدخل مبكر", "علاج وظيفي", "إرشاد أسري"],
            specialties=["تنظيم حسي", "تأخر نمائي"],
            served_needs=["تنظيم حسي", "دعم أسري"],
            min_age_years=0,
            max_age_years=6,
        ),
    }

    _ensure_center_account(db, center=centers["early_intervention"], user=center_rep)

    return SeedContext(
        db=db,
        now=now,
        guardian=guardian,
        secondary_guardian=secondary_guardian,
        specialists=specialists,
        center_rep=center_rep,
        centers=centers,
    )


def _ensure_center_account(db: Session, *, center: Center, user: User) -> None:
    from app.models.center_account import CenterAccountMembership

    existing = db.scalar(
        select(CenterAccountMembership).where(
            CenterAccountMembership.center_id == center.id,
            CenterAccountMembership.user_id == user.id,
        )
    )
    if existing:
        return
    db.add(
        CenterAccountMembership(
            center_id=center.id,
            user_id=user.id,
            account_role="owner",
            is_active=True,
        )
    )


def _upload_file(path: Path, *, filename: str, content_type: str) -> tuple[UploadFile, "object"]:
    handle = path.open("rb")
    size = path.stat().st_size
    upload = UploadFile(file=handle, size=size, filename=filename, headers=Headers({"content-type": content_type}))
    return upload, handle


def upload_report_pdf(ctx: SeedContext, *, child_id: str, report_id: str, version_id: str,
                       asset_filename: str) -> StoredFile:
    path = ASSETS_DIR / asset_filename
    upload, handle = _upload_file(path, filename=asset_filename, content_type="application/pdf")
    try:
        return ctx.report_storage.save_upload(
            upload, child_id=child_id, report_id=report_id, version_id=version_id
        )
    finally:
        handle.close()


def upload_voice_wav(ctx: SeedContext, *, child_id: str, voice_note_id: str) -> StoredFile:
    path = ASSETS_DIR / "demo_voice_sample.wav"
    upload, handle = _upload_file(path, filename="demo_voice_sample.wav", content_type="audio/wav")
    try:
        return ctx.voice_storage.save_upload(upload, child_id=child_id, voice_note_id=voice_note_id)
    finally:
        handle.close()


def add_audit_log(db: Session, *, child_id: str, actor_user_id: str, action: str,
                   entity_type: str, entity_id: str | None, created_at: datetime,
                   details: dict | None = None) -> AccessAuditLog:
    log = AccessAuditLog(
        id=str(uuid.uuid4()),
        child_id=child_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
        created_at=created_at,
    )
    db.add(log)
    db.flush()
    return log


def ensure_favorite(db: Session, *, user_id: str, center_id: str, created_at: datetime) -> None:
    from app.models.center import CenterFavorite

    existing = db.scalar(
        select(CenterFavorite).where(
            CenterFavorite.user_id == user_id, CenterFavorite.center_id == center_id
        )
    )
    if existing:
        return
    db.add(CenterFavorite(user_id=user_id, center_id=center_id, created_at=created_at))


def mark_read(db: Session, *, user_id: str, event_key: str) -> None:
    existing = db.scalar(
        select(NotificationReceipt).where(
            NotificationReceipt.user_id == user_id,
            NotificationReceipt.event_key == event_key,
        )
    )
    if existing:
        return
    db.add(NotificationReceipt(user_id=user_id, event_key=event_key))
