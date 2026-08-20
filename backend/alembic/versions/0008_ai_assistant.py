"""grounded AI assistant threads and messages

Revision ID: 0008_ai_assistant
Revises: 0007_chat
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_ai_assistant"
down_revision: str | None = "0007_chat"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_threads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assistant_threads_child_id"),
        "assistant_threads",
        ["child_id"],
        unique=False,
    )

    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["assistant_threads.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assistant_messages_thread_id"),
        "assistant_messages",
        ["thread_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_assistant_messages_thread_id"),
        table_name="assistant_messages",
    )
    op.drop_table("assistant_messages")
    op.drop_index(
        op.f("ix_assistant_threads_child_id"),
        table_name="assistant_threads",
    )
    op.drop_table("assistant_threads")
