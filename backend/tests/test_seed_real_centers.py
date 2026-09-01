from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.center import Center
from scripts.seed_real_centers import REAL_CENTERS, seed_real_centers


def test_seed_real_centers_is_idempotent():
    with SessionLocal() as db:
        first = seed_real_centers(db, check_migrations=False)
        assert first["created"] == len(REAL_CENTERS)
        assert first["updated"] == 0

        second = seed_real_centers(db, check_migrations=False)
        assert second["created"] == 0
        assert second["updated"] == len(REAL_CENTERS)

        rows = db.scalars(select(Center).where(Center.source_type == "public_research")).all()
        assert len(rows) == len(REAL_CENTERS)


def test_seeded_real_centers_are_tagged_and_sourced():
    with SessionLocal() as db:
        seed_real_centers(db, check_migrations=False)
        rows = db.scalars(select(Center).where(Center.source_type == "public_research")).all()

        assert len(rows) == len(REAL_CENTERS)
        for row in rows:
            assert row.source_type == "public_research"
            assert row.source_urls, f"{row.name} is missing source_urls"
            assert row.last_reviewed_at is not None
            assert row.data_confidence == "high"
            # Real centers must never be pre-marked as verified by Weam merely
            # because public information was found — that is a separate admin step.
            assert row.verification_status == "unverified"


def test_seed_real_centers_covers_both_cities():
    with SessionLocal() as db:
        seed_real_centers(db, check_migrations=False)
        cities = {
            city
            for (city,) in db.execute(
                select(Center.city).where(Center.source_type == "public_research")
            ).all()
        }
        assert cities == {"الرياض", "جدة"}
