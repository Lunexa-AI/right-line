"""
Pytest configuration and fixtures for Gweta tests.

Provides shared fixtures for:
- Mock Redis client (fakeredis)
- Test database connections
- Common test data

Follows .cursorrules: Centralized fixtures, clean test setup.
"""

import pytest
import os


@pytest.fixture
def mock_redis_url(monkeypatch):
    """Set mock Redis URL for testing."""
    # Use fakeredis URL for tests
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/9")  # DB 9 for tests
    return "redis://localhost:6379/9"


@pytest.fixture
async def redis_client():
    """
    Provide fakeredis client for testing.
    
    This avoids requiring actual Redis server during tests.
    """
    from fakeredis import aioredis as fakeredis
    
    # Create fake Redis client
    client = fakeredis.FakeRedis(decode_responses=True)
    
    yield client
    
    # Cleanup - flush all data after test
    await client.flushdb()
    await client.close()


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    # Ensure we're in test mode
    monkeypatch.setenv("RIGHTLINE_APP_ENV", "test")
    
    # Use fake Redis for tests
    if not os.getenv("REDIS_URL"):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/9")
