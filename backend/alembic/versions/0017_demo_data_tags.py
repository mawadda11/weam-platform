"""demo data tagging for safe, scoped seeding and reset

Revision ID: 0017_demo_data_tags
Revises: 0016_center_source_provenance
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0017_demo_data_tags"
down_revision: str | None = "0016_center_source_provenance"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("demo_batch", sa.String(length=60), nullable=True))
    op.create_index(op.f("ix_users_demo_batch"), "users", ["demo_batch"], unique=False)

    op.add_column("children", sa.Column("external_ref", sa.String(length=60), nullable=True))
    op.create_unique_constraint("uq_children_external_ref", "children", ["external_ref"])


def downgrade() -> None:
    op.drop_constraint("uq_children_external_ref", "children", type_="unique")
    op.drop_column("children", "external_ref")
    op.drop_index(op.f("ix_users_demo_batch"), table_name="users")
    op.drop_column("users", "demo_batch")
