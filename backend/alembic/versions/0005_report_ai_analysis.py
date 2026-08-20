"""report AI analysis with human review

Revision ID: 0005_report_ai_analysis
Revises: 0004_goals_timeline
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_report_ai_analysis"
down_revision: str | None = "0004_goals_timeline"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_ai_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("report_version_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("analysis_status", sa.String(length=24), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["report_version_id"],
            ["report_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_report_ai_analyses_child_id"),
        "report_ai_analyses",
        ["child_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_ai_analyses_report_id"),
        "report_ai_analyses",
        ["report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_ai_analyses_report_version_id"),
        "report_ai_analyses",
        ["report_version_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_report_ai_analyses_report_version_id"),
        table_name="report_ai_analyses",
    )
    op.drop_index(
        op.f("ix_report_ai_analyses_report_id"),
        table_name="report_ai_analyses",
    )
    op.drop_index(
        op.f("ix_report_ai_analyses_child_id"),
        table_name="report_ai_analyses",
    )
    op.drop_table("report_ai_analyses")
