from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Weam API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    frontend_origins: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://weam:weam@localhost:5433/weam"

    jwt_secret: str = "replace-me-locally"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    max_failed_login_attempts: int = 5
    login_lockout_minutes: int = 15

    google_client_id: str | None = None
    create_tables_on_startup: bool = False

    storage_root: str = ".weam_storage"
    max_report_upload_mb: int = 15
    max_voice_upload_mb: int = 25
    max_chat_attachment_mb: int = 10

    ai_provider: str = "mock"
    ai_api_key: str | None = None
    ai_model: str = "gemini-2.5-flash"
    ai_timeout_seconds: int = 60
    ai_max_inline_mb: int = 8

    # Free/local speech-to-text.
    # large-v3-turbo is the preferred multilingual quality/speed balance.
    stt_provider: str = "local_whisper"
    stt_api_key: str | None = None
    stt_model: str = "large-v3-turbo"
    stt_fallback_model: str = "small"
    stt_language: str = "auto"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    stt_batch_size: int = 4
    stt_beam_size: int = 1
    stt_vad_min_silence_ms: int = 500
    # Grounded assistant: Gemini Free Tier for synthesis + local retrieval/fallback.
    assistant_provider: str = "gemini"
    assistant_api_key: str | None = None
    assistant_model: str = "gemini-3.6-flash"
    assistant_timeout_seconds: int = 45
    assistant_source_limit: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WEAM_",
        extra="ignore",
    )

    @property
    def frontend_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.frontend_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


_UNSAFE_JWT_SECRETS = {
    "replace-me-locally",
    "replace-with-a-long-random-secret",
    "change-this-to-at-least-32-random-characters",
}


def assert_production_ready(settings: Settings) -> None:
    """Refuse to start in production with development-only defaults.

    Called once at application startup. Has no effect outside
    ``WEAM_ENVIRONMENT=production`` so local development and tests are unaffected.
    """
    if settings.environment != "production":
        return

    problems: list[str] = []
    if settings.jwt_secret in _UNSAFE_JWT_SECRETS or len(settings.jwt_secret) < 32:
        problems.append("WEAM_JWT_SECRET must be a unique random value of at least 32 characters")
    if settings.create_tables_on_startup:
        problems.append(
            "WEAM_CREATE_TABLES_ON_STARTUP must be false in production; "
            "schema changes must go through Alembic migrations"
        )
    if not settings.database_url.startswith("postgresql"):
        problems.append("WEAM_DATABASE_URL must point to PostgreSQL in production")

    if problems:
        raise RuntimeError(
            "Refusing to start: unsafe configuration for production — " + "; ".join(problems)
        )
