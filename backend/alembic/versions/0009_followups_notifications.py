"""follow-ups and notification read receipts

Revision ID: 0009_followups_notifications
Revises: 0008_ai_assistant
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0009_followups_notifications"
down_revision: str | None = "0008_ai_assistant"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "follow_ups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=True),
        sa.Column("source_label", sa.String(length=220), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("completed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("child_id", "due_date", "status", "source_type", "source_id"):
        op.create_index(
            op.f(f"ix_follow_ups_{column}"),
            "follow_ups",
            [column],
            unique=False,
        )

    op.create_table(
        "notification_receipts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("event_key", sa.String(length=180), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "event_key",
            name="uq_notification_receipt_user_event",
        ),
    )
    op.create_index(
        op.f("ix_notification_receipts_user_id"),
        "notification_receipts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_receipts_event_key"),
        "notification_receipts",
        ["event_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notification_receipts_event_key"),
        table_name="notification_receipts",
    )
    op.drop_index(
        op.f("ix_notification_receipts_user_id"),
        table_name="notification_receipts",
    )
    op.drop_table("notification_receipts")

    for column in ("source_id", "source_type", "status", "due_date", "child_id"):
        op.drop_index(op.f(f"ix_follow_ups_{column}"), table_name="follow_ups")
    op.drop_table("follow_ups")
