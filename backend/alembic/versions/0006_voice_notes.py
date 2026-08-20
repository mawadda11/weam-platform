"""voice notes and speech-to-text review

Revision ID: 0006_voice_notes
Revises: 0005_report_ai_analysis
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_voice_notes"
down_revision: str | None = "0005_report_ai_analysis"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voice_notes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("transcription_status", sa.String(length=24), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("transcript_draft", sa.Text(), nullable=True),
        sa.Column("transcript_final", sa.Text(), nullable=True),
        sa.Column("transcript_language", sa.String(length=24), nullable=True),
        sa.Column("stt_provider", sa.String(length=40), nullable=True),
        sa.Column("stt_model", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_voice_notes_child_id"),
        "voice_notes",
        ["child_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_voice_notes_child_id"), table_name="voice_notes")
    op.drop_table("voice_notes")
