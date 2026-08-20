"""authentication and child profile baseline

Revision ID: 0001_auth_child_profile
Revises:
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_auth_child_profile"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=180), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("google_sub", sa.String(length=255), nullable=True),
        sa.Column("auth_provider", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("provider_specialty", sa.String(length=120), nullable=True),
        sa.Column("verification_status", sa.String(length=24), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("google_sub"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    op.create_table(
        "children",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_children_created_by_user_id"), "children", ["created_by_user_id"], unique=False)

    op.create_table(
        "child_identities",
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("preferred_name", sa.String(length=120), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("child_id"),
    )

    op.create_table(
        "care_profiles",
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("needs", sa.JSON(), nullable=False),
        sa.Column("support_requirements", sa.JSON(), nullable=False),
        sa.Column("services", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("child_id"),
    )

    op.create_table(
        "guardian_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("guardian_user_id", sa.String(length=36), nullable=False),
        sa.Column("guardian_type", sa.String(length=24), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guardian_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "guardian_user_id", name="uq_child_guardian"),
    )
    op.create_index(op.f("ix_guardian_memberships_child_id"), "guardian_memberships", ["child_id"], unique=False)
    op.create_index(
        op.f("ix_guardian_memberships_guardian_user_id"),
        "guardian_memberships",
        ["guardian_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_guardian_memberships_guardian_user_id"), table_name="guardian_memberships")
    op.drop_index(op.f("ix_guardian_memberships_child_id"), table_name="guardian_memberships")
    op.drop_table("guardian_memberships")
    op.drop_table("care_profiles")
    op.drop_table("child_identities")
    op.drop_index(op.f("ix_children_created_by_user_id"), table_name="children")
    op.drop_table("children")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
