"""center source and freshness provenance

Revision ID: 0016_center_source_provenance
Revises: 0015_auth_hardening
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0016_center_source_provenance"
down_revision: str | None = "0015_auth_hardening"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "centers",
        sa.Column("source_type", sa.String(length=24), server_default="synthetic_demo", nullable=False),
    )
    op.add_column(
        "centers",
        sa.Column("source_urls", sa.JSON(), server_default="[]", nullable=False),
    )
    op.add_column("centers", sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("centers", sa.Column("data_confidence", sa.String(length=16), nullable=True))
    op.add_column(
        "centers",
        sa.Column("listing_claimed", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index(op.f("ix_centers_source_type"), "centers", ["source_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_centers_source_type"), table_name="centers")
    op.drop_column("centers", "listing_claimed")
    op.drop_column("centers", "data_confidence")
    op.drop_column("centers", "last_reviewed_at")
    op.drop_column("centers", "source_urls")
    op.drop_column("centers", "source_type")
