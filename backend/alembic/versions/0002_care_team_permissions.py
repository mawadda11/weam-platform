"""care team invitations permissions and audit log

Revision ID: 0002_care_team_permissions
Revises: 0001_auth_child_profile
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_care_team_permissions"
down_revision: str | None = "0001_auth_child_profile"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("guardian_memberships", sa.Column("role_label", sa.String(length=120), nullable=True))
    op.add_column(
        "guardian_memberships",
        sa.Column("access_status", sa.String(length=24), nullable=False, server_default="active"),
    )
    op.add_column("guardian_memberships", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("guardian_memberships", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("guardian_memberships", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "care_team_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("invited_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("role_label", sa.String(length=120), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("access_status", sa.String(length=24), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "user_id", name="uq_child_care_member"),
    )
    op.create_index(op.f("ix_care_team_memberships_child_id"), "care_team_memberships", ["child_id"], unique=False)
    op.create_index(op.f("ix_care_team_memberships_user_id"), "care_team_memberships", ["user_id"], unique=False)
    op.create_index(op.f("ix_care_team_memberships_access_status"), "care_team_memberships", ["access_status"], unique=False)

    op.create_table(
        "care_invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("invited_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("target_role", sa.String(length=32), nullable=False),
        sa.Column("role_label", sa.String(length=120), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invitation_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_care_invitations_child_id"), "care_invitations", ["child_id"], unique=False)
    op.create_index(op.f("ix_care_invitations_email"), "care_invitations", ["email"], unique=False)
    op.create_index(op.f("ix_care_invitations_status"), "care_invitations", ["status"], unique=False)

    op.create_table(
        "access_audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_access_audit_logs_child_id"), "access_audit_logs", ["child_id"], unique=False)
    op.create_index(op.f("ix_access_audit_logs_actor_user_id"), "access_audit_logs", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_access_audit_logs_action"), "access_audit_logs", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_access_audit_logs_action"), table_name="access_audit_logs")
    op.drop_index(op.f("ix_access_audit_logs_actor_user_id"), table_name="access_audit_logs")
    op.drop_index(op.f("ix_access_audit_logs_child_id"), table_name="access_audit_logs")
    op.drop_table("access_audit_logs")

    op.drop_index(op.f("ix_care_invitations_status"), table_name="care_invitations")
    op.drop_index(op.f("ix_care_invitations_email"), table_name="care_invitations")
    op.drop_index(op.f("ix_care_invitations_child_id"), table_name="care_invitations")
    op.drop_table("care_invitations")

    op.drop_index(op.f("ix_care_team_memberships_access_status"), table_name="care_team_memberships")
    op.drop_index(op.f("ix_care_team_memberships_user_id"), table_name="care_team_memberships")
    op.drop_index(op.f("ix_care_team_memberships_child_id"), table_name="care_team_memberships")
    op.drop_table("care_team_memberships")

    op.drop_column("guardian_memberships", "revoked_at")
    op.drop_column("guardian_memberships", "expires_at")
    op.drop_column("guardian_memberships", "accepted_at")
    op.drop_column("guardian_memberships", "access_status")
    op.drop_column("guardian_memberships", "role_label")
