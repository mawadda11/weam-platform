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

    google_client_id: str | None = None
    create_tables_on_startup: bool = False

    storage_root: str = ".weam_storage"
    max_report_upload_mb: int = 15
    max_voice_upload_mb: int = 25

    ai_provider: str = "mock"
    ai_api_key: str | None = None
    ai_model: str = "gemini-2.5-flash"
    ai_timeout_seconds: int = 60
    ai_max_inline_mb: int = 8

    # Provider-independent speech-to-text boundary.
    # "mock" keeps local development deterministic until a production
    # provider is configured.
    stt_provider: str = "mock"
    stt_api_key: str | None = None
    stt_model: str = "provider-default"
    stt_language: str = "ar"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WEAM_",
        extra="ignore",
    )

    @property
    def frontend_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
