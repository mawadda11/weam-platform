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
