"""Runtime configuration for the backend.

All configuration is loaded from environment variables via Pydantic
Settings. The model is the single source of truth for what the service
expects to find in the environment - if a value is not declared here, the
rest of the codebase must not read it directly from `os.environ`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, populated from environment variables.

    The ``.env`` file at the repository root is loaded automatically when
    present; in production all values are expected to come from real
    environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # --- General ---
    environment: Literal["dev", "test", "prod"] = Field(default="dev")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Anthropic / Claude ---
    anthropic_api_key: str = Field(default="")
    model_orchestrator: str = Field(default="claude-opus-4-7")
    model_creative_director: str = Field(default="claude-opus-4-7")
    model_planner: str = Field(default="claude-sonnet-4-6")
    model_specialist: str = Field(default="claude-sonnet-4-6")
    model_lightweight: str = Field(default="claude-haiku-4-5-20251001")

    # --- Postgres ---
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_user: str = Field(default="videoeditor")
    postgres_password: str = Field(default="videoeditor")
    postgres_db: str = Field(default="videoeditor")

    # --- Redis ---
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)

    # --- Celery ---
    # When ``celery_eager`` is True, ``.delay()`` runs the task
    # synchronously in the current process - convenient for tests
    # and ``make dev``. Set to False in production so the API enqueues
    # work and the worker process picks it up.
    celery_eager: bool = Field(default=True)

    # --- MinIO / S3 ---
    s3_endpoint_url: str = Field(default="http://localhost:9000")
    s3_access_key: str = Field(default="videoeditor")
    s3_secret_key: str = Field(default="videoeditor")
    s3_region: str = Field(default="us-east-1")
    s3_bucket_assets: str = Field(default="assets")
    s3_bucket_renders: str = Field(default="renders")
    s3_use_ssl: bool = Field(default=False)

    @property
    def database_url(self) -> str:
        """SQLAlchemy async DSN for the configured Postgres instance."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Synchronous DSN, used by Alembic migrations."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Redis DSN used by Celery broker and result backend."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Cached so that the environment is read once. Tests can override values
    with :meth:`Settings.model_copy` and inject the result via FastAPI's
    dependency overrides.
    """
    return Settings()
