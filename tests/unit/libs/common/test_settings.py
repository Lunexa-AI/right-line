"""Tests for application settings."""

import os
import tempfile

import pytest
from pydantic import ValidationError

from libs.common.settings import Settings


class TestSettings:
    """Test settings configuration."""

    def test_settings_with_minimal_env(self):
        """Test settings with minimal required environment variables."""
        env_vars = {
            "RIGHTLINE_SECRET_KEY": "a" * 32,  # 32 characters minimum
            "RIGHTLINE_DATABASE_URL": "postgresql://user:pass@localhost/db",
            "RIGHTLINE_REDIS_URL": "redis://localhost:6379/0",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
            env_file = f.name

        try:
            settings = Settings(_env_file=env_file)
            assert settings.secret_key == "a" * 32
            assert settings.database_url == "postgresql://user:pass@localhost/db"
            assert settings.redis_url == "redis://localhost:6379/0"
            assert settings.app_env == "development"  # default
        finally:
            os.unlink(env_file)

    def test_settings_validation_secret_key_too_short(self):
        """Test that short secret keys are rejected."""
        env_vars = {
            "RIGHTLINE_SECRET_KEY": "short",
            "RIGHTLINE_DATABASE_URL": "postgresql://user:pass@localhost/db",
            "RIGHTLINE_REDIS_URL": "redis://localhost:6379/0",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
            env_file = f.name

        try:
            with pytest.raises(ValidationError) as exc_info:
                Settings(_env_file=env_file)
            assert "Secret key must be at least 32 characters" in str(exc_info.value)
        finally:
            os.unlink(env_file)

    def test_settings_cors_origins_parsing(self):
        """Test CORS origins parsing from comma-separated string."""
        env_vars = {
            "RIGHTLINE_SECRET_KEY": "a" * 32,
            "RIGHTLINE_DATABASE_URL": "postgresql://user:pass@localhost/db",
            "RIGHTLINE_REDIS_URL": "redis://localhost:6379/0",
            "RIGHTLINE_CORS_ORIGINS": "http://localhost:3000,http://localhost:8080",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
            env_file = f.name

        try:
            settings = Settings(_env_file=env_file)
            assert settings.cors_origins == ["http://localhost:3000", "http://localhost:8080"]
        finally:
            os.unlink(env_file)

    def test_settings_environment_properties(self):
        """Test environment detection properties."""
        # Development
        dev_settings = Settings(
            secret_key="a" * 32,
            database_url="postgresql://user:pass@localhost/db",
            redis_url="redis://localhost:6379/0",
            app_env="development",
        )
        assert dev_settings.is_development is True
        assert dev_settings.is_production is False

        # Production
        prod_settings = Settings(
            secret_key="a" * 32,
            database_url="postgresql://user:pass@localhost/db",
            redis_url="redis://localhost:6379/0",
            app_env="production",
        )
        assert prod_settings.is_development is False
        assert prod_settings.is_production is True

    def test_database_url_sync_property(self):
        """Test synchronous database URL generation."""
        settings = Settings(
            secret_key="a" * 32,
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            redis_url="redis://localhost:6379/0",
        )
        assert settings.database_url_sync == "postgresql://user:pass@localhost/db"

    def test_settings_defaults(self):
        """Test default values are set correctly."""
        settings = Settings(
            secret_key="a" * 32,
            database_url="postgresql://user:pass@localhost/db",
            redis_url="redis://localhost:6379/0",
        )

        # Check some defaults
        assert settings.app_env == "development"
        assert settings.log_level == "INFO"
        assert settings.api_port == 8000
        assert settings.worker_concurrency == 4
        assert settings.device == "cpu"
        assert settings.embedding_model == "all-MiniLM-L6-v2"

    def test_settings_env_prefix(self):
        """Test that environment variables use RIGHTLINE_ prefix."""
        # Set environment variable
        os.environ["RIGHTLINE_API_PORT"] = "9000"

        try:
            settings = Settings(
                secret_key="a" * 32,
                database_url="postgresql://user:pass@localhost/db",
                redis_url="redis://localhost:6379/0",
            )
            assert settings.api_port == 9000
        finally:
            # Clean up
            os.environ.pop("RIGHTLINE_API_PORT", None)
