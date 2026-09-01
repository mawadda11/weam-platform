"""widen centers.phone to fit real multi-number published contact info

Revision ID: 0018_widen_center_phone
Revises: 0017_demo_data_tags

Found by running the real-center seed against actual PostgreSQL: SQLite (used
by the test suite) does not enforce VARCHAR length, so this only surfaced here.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0018_widen_center_phone"
down_revision: str | None = "0017_demo_data_tags"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("centers", "phone", type_=sa.String(length=120), existing_type=sa.String(length=40))


def downgrade() -> None:
    op.alter_column("centers", "phone", type_=sa.String(length=40), existing_type=sa.String(length=120))
