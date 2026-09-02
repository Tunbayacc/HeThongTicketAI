from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "AI Customer Support"
    environment: str = "development"
    log_level: str = "INFO"
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"]
    )

    # Database
    database_url: str = (
        "postgresql+asyncpg://ai_support:ai_support@localhost:5432/ai_support"
    )

    # Auth (used from S1 onward; keep defaults so S0 boots)
    jwt_secret_key: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False

    # Auth lockout + refresh-cookie name (S1; defaults keep dev simple)
    refresh_token_cookie_name: str = "refresh_token"
    max_login_attempts: int = 5
    account_lock_minutes: int = 15

    # AI provider (real use from S4 onward)
    ai_provider: str = "mock"  # "gemini" | "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    ai_timeout_seconds: int = 30
    ai_low_confidence_threshold: float = 0.70

    # Uploads (real use from S2 onward)
    max_upload_size_mb: int = 10
    allowed_file_types: str = "pdf,png,jpg,jpeg,txt,docx"

    # Seed admin (created from Task 5 onward)
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = ""  # must be provided via env, never hard-coded

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, v):
        # pydantic-settings treats list[str] as a JSON-encoded complex value, but the
        # env/`docker-compose` value is a plain comma-separated string (e.g.
        # "http://localhost:5173,http://localhost:8080"). NoDecode keeps the raw
        # string, which we split here so both forms work.
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
