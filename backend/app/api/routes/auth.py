from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.constants import UserRole, VerificationStatus
from app.db.session import get_db
from app.models.auth_token import RefreshTokenRecord
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    GoogleAuthRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    UserPublic,
)
from app.services.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _issue_tokens(db: Session, user: User) -> AuthResponse:
    record = RefreshTokenRecord(
        id=str(uuid.uuid4()),
        user_id=user.id,
        expires_at=_utcnow() + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(record)
    db.commit()
    return AuthResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, user.role, jti=record.id),
        user=UserPublic.model_validate(user),
    )


def _register_failed_login(db: Session, user: User) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.max_failed_login_attempts:
        user.locked_until = _utcnow() + timedelta(minutes=settings.login_lockout_minutes)
    db.commit()


def _clear_login_lock(db: Session, user: User) -> None:
    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = str(payload.email).lower().strip()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    is_guardian = payload.role == UserRole.GUARDIAN
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role.value,
        provider_specialty=payload.provider_specialty.strip() if payload.provider_specialty else None,
        verification_status=(
            VerificationStatus.VERIFIED.value if is_guardian else VerificationStatus.UNVERIFIED.value
        ),
        auth_provider="password",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(db, user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = str(payload.email).lower().strip()
    user = db.scalar(select(User).where(User.email == email))

    if user and user.locked_until and _utcnow() < _as_aware(user.locked_until):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
        )

    if not user or not verify_password(payload.password, user.password_hash):
        if user:
            _register_failed_login(db, user)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    _clear_login_lock(db, user)
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=AuthResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> AuthResponse:
    claims = decode_token(payload.refresh_token, "refresh")
    jti = claims.get("jti") if claims else None
    if not claims or not jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    record = db.get(RefreshTokenRecord, jti)
    if (
        not record
        or record.revoked_at is not None
        or record.user_id != claims["sub"]
        or _as_aware(record.expires_at) <= _utcnow()
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is unavailable")

    # Rotate: this refresh token is single-use.
    record.revoked_at = _utcnow()
    db.commit()
    return _issue_tokens(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> None:
    claims = decode_token(payload.refresh_token, "refresh")
    jti = claims.get("jti") if claims else None
    if jti:
        record = db.get(RefreshTokenRecord, jti)
        if record and record.revoked_at is None:
            record.revoked_at = _utcnow()
            db.commit()
    # Always 204: logout must not reveal whether the token was valid.
    return None


@router.post("/google", response_model=AuthResponse)
def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Sign-In is not configured",
        )

    # Imported lazily so local email/password development does not depend on Google credentials.
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google authentication dependency is not installed",
        ) from exc

    try:
        info = id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except Exception as exc:  # Google library exposes multiple verification exceptions.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credential") from exc

    email = str(info.get("email", "")).lower().strip()
    google_sub = str(info.get("sub", "")).strip()
    full_name = str(info.get("name") or email.split("@")[0]).strip()
    email_verified = bool(info.get("email_verified"))
    if not email or not google_sub or not email_verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account is not verified")

    user = db.scalar(select(User).where(User.google_sub == google_sub))
    if not user:
        user = db.scalar(select(User).where(User.email == email))
        if user:
            user.google_sub = google_sub
            user.auth_provider = "password+google" if user.password_hash else "google"
        else:
            if payload.role is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="role is required for first Google sign-in",
                )
            if payload.role == UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Admin accounts cannot be created through public registration",
                )
            if payload.role == UserRole.CARE_PROVIDER and not payload.provider_specialty:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="provider_specialty is required for care providers",
                )
            user = User(
                email=email,
                full_name=full_name,
                google_sub=google_sub,
                auth_provider="google",
                role=payload.role.value,
                provider_specialty=(
                    payload.provider_specialty.strip() if payload.provider_specialty else None
                ),
                verification_status=(
                    VerificationStatus.VERIFIED.value
                    if payload.role == UserRole.GUARDIAN
                    else VerificationStatus.UNVERIFIED.value
                ),
            )
            db.add(user)

        db.commit()
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return _issue_tokens(db, user)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> User:
    return user
