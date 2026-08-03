"""Application configuration loaded from environment variables / .env file.

All runtime *secrets* live here (env). All *business* parameters (prompts,
templates, watermark settings, feature toggles) are stored in the database and
editable from the web panel — see ``shared.models.setting``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    app_name: str = "CityNews"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me"
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: str = "http://localhost:3000"
    default_language: str = "ru"
    supported_languages: str = "ru,en"

    # Postgres
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "citynews"
    postgres_password: str = "citynews"
    postgres_db: str = "citynews"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Auth
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    jwt_algorithm: str = "HS256"

    # First super admin
    first_superadmin_email: str = "admin@example.com"
    first_superadmin_password: str = "ChangeMe123!"

    # Telegram
    telegram_bot_token: str = ""
    telegram_moderation_group_id: int = 0
    telegram_webhook_url: str = ""
    admin_panel_url: str = "http://localhost:3000"
    #: Bot Client ID for the new Telegram Login (OIDC) library. From @BotFather
    #: → Bot Settings → Web Login. Used as the expected ``aud`` of ``id_token``.
    telegram_client_id: int = 0

    # AI
    default_ai_provider: str = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    local_llm_base_url: str = "http://localhost:11434/v1"
    local_llm_model: str = "llama3.1"

    # Media
    media_root: str = "./data/media"
    max_upload_size_mb: int = 50
    ffmpeg_binary: str = "ffmpeg"

    # Backups
    backup_root: str = "./data/backups"
    backup_cron_hour: int = 3

    # ── Derived values ───────────────────────────────────────────────────────
    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy DSN (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Synchronous DSN (used by Alembic migrations)."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]

    @property
    def languages_list(self) -> list[str]:
        return [lang.strip() for lang in self.supported_languages.split(",") if lang.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()


settings = get_settings()
