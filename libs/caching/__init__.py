"""
Caching utilities for Gweta Legal AI.

This module provides multi-level caching capabilities:
- Redis client management
- Semantic caching (exact + similarity matching)
- Intent and embedding caching

Follows .cursorrules: async-first, connection pooling, graceful degradation.
"""

from libs.caching.redis_client import get_redis_client

__all__ = ["get_redis_client"]
