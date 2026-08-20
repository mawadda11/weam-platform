"""goals and progress history

Revision ID: 0004_goals_timeline
Revises: 0003_reports
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_goals_timeline"
down_revision: str | None = "0003_reports"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("assigned_to_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_goal_progress_percent",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_goals_child_id"), "goals", ["child_id"], unique=False)
    op.create_index(op.f("ix_goals_status"), "goals", ["status"], unique=False)

    op.create_table(
        "goal_updates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("goal_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_goal_update_progress_percent",
        ),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_goal_updates_goal_id"),
        "goal_updates",
        ["goal_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_goal_updates_goal_id"), table_name="goal_updates")
    op.drop_table("goal_updates")
    op.drop_index(op.f("ix_goals_status"), table_name="goals")
    op.drop_index(op.f("ix_goals_child_id"), table_name="goals")
    op.drop_table("goals")
