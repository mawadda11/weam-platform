from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Weam API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    frontend_origins: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://weam:weam@localhost:5432/weam"

    jwt_secret: str = "replace-me-locally"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    google_client_id: str | None = None
    create_tables_on_startup: bool = True

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
