from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Weam API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://weam:weam@localhost:5432/weam"
    jwt_secret: str = "replace-me-locally"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WEAM_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
