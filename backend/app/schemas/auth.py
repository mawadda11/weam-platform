from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.constants import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=180)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    provider_specialty: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_care_provider(self):
        if self.role == UserRole.CARE_PROVIDER and not self.provider_specialty:
            raise ValueError("provider_specialty is required for care providers")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str = Field(min_length=20)
    role: UserRole | None = None
    provider_specialty: str | None = Field(default=None, max_length=120)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    provider_specialty: str | None = None
    verification_status: str
    auth_provider: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic
