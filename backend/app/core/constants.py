from enum import StrEnum


class UserRole(StrEnum):
    GUARDIAN = "guardian"
    CARE_PROVIDER = "care_provider"
    CENTER = "center"
    ADMIN = "admin"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"


class GuardianType(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class AccessStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class CarePermission(StrEnum):
    VIEW_PROFILE = "view_profile"
    VIEW_CARE_TEAM = "view_care_team"
    VIEW_REPORTS = "view_reports"
    UPLOAD_REPORTS = "upload_reports"
    VIEW_GOALS = "view_goals"
    MANAGE_GOALS = "manage_goals"
    VIEW_TIMELINE = "view_timeline"
    VIEW_VOICE_NOTES = "view_voice_notes"
    CREATE_VOICE_NOTES = "create_voice_notes"
    MESSAGE_TEAM = "message_team"
    MANAGE_CHILD = "manage_child"
    MANAGE_CARE_TEAM = "manage_care_team"
    MANAGE_PERMISSIONS = "manage_permissions"


class GoalStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAUSED = "paused"
