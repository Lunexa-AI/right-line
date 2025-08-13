"""Application settings using Pydantic BaseSettings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="RIGHTLINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core application settings
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    debug: bool = False
    secret_key: str = Field(..., min_length=32)

    # Database settings
    database_url: str = Field(..., description="PostgreSQL connection string")
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis settings
    redis_url: str = Field(..., description="Redis connection string")
    redis_max_connections: int = 20

    # Search engines
    meilisearch_url: str = "http://localhost:7700"
    meilisearch_key: str | None = None
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # Object storage
    minio_url: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "rightline-documents"

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 2
    api_timeout_ms: int = 2000

    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Microservices
    retrieval_port: int = 8001
    summarizer_port: int = 8002

    # Worker settings
    worker_concurrency: int = 4
    worker_max_retries: int = 3
    worker_retry_delay: int = 5

    # ML/AI settings
    model_path: str = "/app/models"
    device: Literal["cpu", "cuda"] = "cpu"
    batch_size: int = 8
    max_length: int = 512
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Cache settings
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 1000

    # Channel integrations
    whatsapp_token: str | None = None
    whatsapp_phone_id: str | None = None
    whatsapp_verify_token: str | None = None
    telegram_token: str | None = None

    # Monitoring
    sentry_dsn: str | None = None
    metrics_enabled: bool = True
    metrics_port: int = 9090
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"

    # Security
    jwt_secret: str | None = None
    jwt_expire_minutes: int = 60

    # External APIs
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Development
    reload: bool = False
    profile: bool = False

    # Testing
    test_database_url: str | None = None

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @validator("secret_key")
    def validate_secret_key(cls, v):
        """Ensure secret key is strong enough."""
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "production"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL (for Alembic)."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience alias
settings = get_settings()
