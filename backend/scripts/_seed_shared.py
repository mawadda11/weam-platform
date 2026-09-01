"""Shared helpers for the standalone seeding scripts in this directory."""
from __future__ import annotations

import os

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.core.config import get_settings
from app.db.session import engine


def assert_migrations_at_head() -> None:
    """Refuse to proceed unless the database is on the latest Alembic revision.

    Seeding must never run ahead of migrations (and must never fall back to
    ``Base.metadata.create_all()``), so every seed script checks this first.
    """
    settings = get_settings()
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    script = ScriptDirectory.from_config(cfg)
    script_heads = set(script.get_heads())

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        db_heads = set(context.get_current_heads())

    if db_heads != script_heads:
        raise RuntimeError(
            "Database is not at the latest Alembic revision. "
            f"Database heads: {db_heads or '(none)'}; expected: {script_heads}. "
            "Run `alembic upgrade head` before seeding."
        )
