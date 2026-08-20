"""Create synthetic demo data for local development only."""

from sqlalchemy import select

import app.models  # noqa: F401
from app.core.constants import GuardianType, UserRole, VerificationStatus
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.child import CareProfile, Child, ChildIdentity, GuardianMembership
from app.models.user import User
from app.services.security import hash_password

DEMO_EMAIL = "guardian@weam.demo"
DEMO_PASSWORD = "WeamDemo123!"


def add_child(db, guardian: User, *, name: str, conditions: list[str], needs: list[str], services: list[str]):
    child = Child(created_by_user_id=guardian.id)
    child.identity = ChildIdentity(first_name=name)
    child.care_profile = CareProfile(
        conditions=conditions,
        needs=needs,
        support_requirements=[],
        services=services,
        summary="بيانات صناعية مخصصة لاختبار وئام فقط.",
    )
    membership = GuardianMembership(
        child=child,
        guardian_user_id=guardian.id,
        guardian_type=GuardianType.PRIMARY.value,
    )
    db.add_all([child, membership])


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        guardian = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if not guardian:
            guardian = User(
                email=DEMO_EMAIL,
                full_name="ولي أمر تجريبي",
                password_hash=hash_password(DEMO_PASSWORD),
                role=UserRole.GUARDIAN.value,
                verification_status=VerificationStatus.VERIFIED.value,
                auth_provider="password",
            )
            db.add(guardian)
            db.flush()

            add_child(
                db,
                guardian,
                name="طفل السمع",
                conditions=["ضعف سمع"],
                needs=["دعم التواصل", "متابعة سمعية"],
                services=["تخاطب", "سمعيات"],
            )
            add_child(
                db,
                guardian,
                name="طفل النمو",
                conditions=["اضطراب طيف التوحد"],
                needs=["تنظيم حسي", "روتين واضح"],
                services=["علاج وظيفي", "سلوك"],
            )
            add_child(
                db,
                guardian,
                name="طفل الحركة",
                conditions=["احتياج حركي"],
                needs=["دعم الحركة"],
                services=["علاج طبيعي"],
            )
            db.commit()

        print("Synthetic demo account ready")
        print(f"Email: {DEMO_EMAIL}")
        print(f"Password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
