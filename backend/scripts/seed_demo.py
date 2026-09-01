"""Create the four-child synthetic demonstration environment.

See docs/SEED_DATA_ARCHITECTURE.md for the design behind this script.

Usage (from backend/):
    .venv\\Scripts\\python.exe -m scripts.seed_demo              # create/skip-existing
    .venv\\Scripts\\python.exe -m scripts.seed_demo --rebuild     # clean rebuild of each demo child
    .venv\\Scripts\\python.exe -m scripts.seed_demo --reset       # delete demo data only, no recreate
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.center import Center
from app.models.child import Child
from app.models.user import User
from scripts._seed_shared import assert_migrations_at_head
from scripts.demo_data import lama, omar, rawan, youssef
from scripts.demo_data.shared import DEMO_BATCH, DEMO_PASSWORD, SeedContext, build_pool

CHILD_BUILDERS = {
    lama.EXTERNAL_REF: lama.build,
    youssef.EXTERNAL_REF: youssef.build,
    rawan.EXTERNAL_REF: rawan.build,
    omar.EXTERNAL_REF: omar.build,
}


def _delete_demo_data(db: Session) -> tuple[int, int, int]:
    """Delete demo children (cascades their whole subtree), then demo users, then
    demo centers. Order matters — see docs/SEED_DATA_ARCHITECTURE.md §5."""
    children = db.scalars(select(Child).where(Child.external_ref.in_(CHILD_BUILDERS.keys()))).all()
    for child in children:
        db.delete(child)
    db.flush()

    users = db.scalars(select(User).where(User.demo_batch == DEMO_BATCH)).all()
    for user in users:
        db.delete(user)
    db.flush()

    centers = db.scalars(select(Center).where(Center.source_type == "synthetic_demo")).all()
    for center in centers:
        db.delete(center)
    db.flush()

    return len(children), len(users), len(centers)


def run_reset(db: Session) -> None:
    deleted_children, deleted_users, deleted_centers = _delete_demo_data(db)
    db.commit()
    print(f"Reset: removed {deleted_children} demo children, {deleted_users} demo users, "
          f"{deleted_centers} demo centers.")


def run_seed(db: Session, *, rebuild: bool) -> None:
    now = datetime.now(timezone.utc)

    if rebuild:
        existing = db.scalars(select(Child).where(Child.external_ref.in_(CHILD_BUILDERS.keys()))).all()
        for child in existing:
            db.delete(child)
        db.flush()

    ctx: SeedContext = build_pool(db, now=now)

    created, skipped = [], []
    for ref, builder in CHILD_BUILDERS.items():
        already = db.scalar(select(Child.id).where(Child.external_ref == ref))
        if already:
            skipped.append(ref)
            continue
        builder(ctx)
        db.flush()
        created.append(ref)

    db.commit()
    print(f"Demo seed complete. Created: {created or 'none'}. Already present (skipped): {skipped or 'none'}.")
    print(f"Demo guardian login: guardian@weam.demo / {DEMO_PASSWORD}")
    print("Other demo accounts (same password): guardian2@, slp@, pt@, edu@, ot@, center@weam.demo")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true",
                         help="Delete and recreate each demo child's full subtree.")
    parser.add_argument("--reset", action="store_true",
                         help="Delete all demo data (children, users, centers) and exit without recreating.")
    args = parser.parse_args()

    settings = get_settings()
    if settings.environment == "production" and os.environ.get("WEAM_ALLOW_DEMO_SEED") != "true":
        raise SystemExit(
            "Refusing to run demo seeding in production without explicit override. "
            "Set WEAM_ALLOW_DEMO_SEED=true if this is intentional."
        )

    assert_migrations_at_head()

    with SessionLocal() as db:
        if args.reset:
            run_reset(db)
        else:
            run_seed(db, rebuild=args.rebuild)


if __name__ == "__main__":
    main()
