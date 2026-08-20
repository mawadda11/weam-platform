"""reports and immutable report versions

Revision ID: 0003_reports
Revises: 0002_care_team_permissions
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_reports"
down_revision: str | None = "0002_care_team_permissions"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("report_type", sa.String(length=80), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("source_label", sa.String(length=180), nullable=True),
        sa.Column("visibility", sa.String(length=24), nullable=False),
        sa.Column("allowed_user_ids", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_child_id"), "reports", ["child_id"], unique=False)
    op.create_index(op.f("ix_reports_report_type"), "reports", ["report_type"], unique=False)

    op.create_table(
        "report_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("storage_key", sa.String(length=700), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "version_number", name="uq_report_version_number"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(op.f("ix_report_versions_report_id"), "report_versions", ["report_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_report_versions_report_id"), table_name="report_versions")
    op.drop_table("report_versions")
    op.drop_index(op.f("ix_reports_report_type"), table_name="reports")
    op.drop_index(op.f("ix_reports_child_id"), table_name="reports")
    op.drop_table("reports")
