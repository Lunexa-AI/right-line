"""Application settings for Vercel + Milvus + OpenAI architecture."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings optimized for serverless deployment."""

    model_config = SettingsConfigDict(
        env_prefix="RIGHTLINE_",
        env_file=None,  # Disable .env file loading temporarily
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core application settings
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    debug: bool = False
    secret_key: str = Field(..., min_length=32)

    # CORS - use string to avoid JSON parsing issues
    cors_origins_str: str = Field(default="http://localhost:3000,https://localhost:3000", alias="cors_origins")
    
    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from string."""
        if not self.cors_origins_str.strip():
            return ["http://localhost:3000", "https://localhost:3000"]
        return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]

    # Channel integrations
    whatsapp_verify_token: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None

    # Monitoring
    sentry_dsn: str | None = None

    # RAG Configuration
    search_top_k: int = 20
    rerank_top_k: int = 10
    high_confidence_threshold: float = 0.8
    low_confidence_threshold: float = 0.4


# OpenAI and Milvus settings are handled via environment variables directly
# since they don't use the RIGHTLINE_ prefix:
# - OPENAI_API_KEY
# - OPENAI_MODEL  
# - OPENAI_MAX_TOKENS
# - OPENAI_EMBEDDING_MODEL
# - MILVUS_ENDPOINT
# - MILVUS_TOKEN
# - MILVUS_COLLECTION_NAME



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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience alias
settings = get_settings()
