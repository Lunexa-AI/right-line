"""Analytics and feedback system using Vercel KV.

This module provides lightweight analytics and feedback collection
for the RightLine serverless MVP. Uses Vercel KV (Redis-compatible)
for fast, serverless-friendly storage.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

# Vercel KV configuration
KV_REST_API_URL = os.environ.get("KV_REST_API_URL")
KV_REST_API_TOKEN = os.environ.get("KV_REST_API_TOKEN")

# Fallback to mock if KV not configured (for local development)
MOCK_KV = not (KV_REST_API_URL and KV_REST_API_TOKEN)

if MOCK_KV:
    logger.warning("Vercel KV not configured, using in-memory mock for analytics")
    _mock_storage: Dict[str, Any] = {}


class QueryLog(BaseModel):
    """Model for query log entries."""
    
    request_id: str
    timestamp: float  # Unix timestamp for easy sorting
    user_hash: str
    channel: str
    query_text: str = Field(max_length=1000)
    response_topic: Optional[str] = None
    confidence: Optional[float] = None
    response_time_ms: int
    status: str  # success, error, no_match
    session_id: Optional[str] = None


class FeedbackEntry(BaseModel):
    """Model for feedback entries."""
    
    request_id: str
    timestamp: float
    user_hash: str
    rating: int = Field(ge=-1, le=1)  # -1 (negative), 0 (neutral), 1 (positive)
    comment: Optional[str] = Field(None, max_length=500)


@dataclass
class AnalyticsSummary:
    """Summary statistics for analytics dashboard."""
    
    total_queries: int
    unique_users: int
    avg_response_time_ms: float
    success_rate: float
    top_topics: List[Dict[str, Any]]
    feedback_stats: Dict[str, int]
    time_period: str


def hash_user_id(user_id: str, secret_key: str) -> str:
    """Create HMAC hash of user ID for privacy."""
    return hmac.new(
        secret_key.encode(),
        user_id.encode(),
        hashlib.sha256
    ).hexdigest()[:16]


async def _kv_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """Set a value in Vercel KV."""
    if MOCK_KV:
        _mock_storage[key] = value
        return True
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            data = {"value": json.dumps(value) if not isinstance(value, str) else value}
            if ttl:
                data["ttl"] = ttl
            
            response = await client.post(
                f"{KV_REST_API_URL}/set/{key}",
                headers={"Authorization": f"Bearer {KV_REST_API_TOKEN}"},
                json=data,
            )
            return response.status_code == 200
    except Exception as e:
        logger.error("Failed to set KV value", key=key, error=str(e))
        return False


async def _kv_get(key: str) -> Optional[Any]:
    """Get a value from Vercel KV."""
    if MOCK_KV:
        return _mock_storage.get(key)
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{KV_REST_API_URL}/get/{key}",
                headers={"Authorization": f"Bearer {KV_REST_API_TOKEN}"},
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("result")
            return None
    except Exception as e:
        logger.error("Failed to get KV value", key=key, error=str(e))
        return None


async def _kv_lpush(key: str, value: Any) -> bool:
    """Push a value to the left of a list in Vercel KV."""
    if MOCK_KV:
        if key not in _mock_storage:
            _mock_storage[key] = []
        _mock_storage[key].insert(0, value)
        # Keep only last 1000 entries in mock
        if len(_mock_storage[key]) > 1000:
            _mock_storage[key] = _mock_storage[key][:1000]
        return True
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{KV_REST_API_URL}/lpush/{key}",
                headers={"Authorization": f"Bearer {KV_REST_API_TOKEN}"},
                json={"value": json.dumps(value)},
            )
            return response.status_code == 200
    except Exception as e:
        logger.error("Failed to lpush KV value", key=key, error=str(e))
        return False


async def _kv_lrange(key: str, start: int = 0, stop: int = -1) -> List[Any]:
    """Get a range of values from a list in Vercel KV."""
    if MOCK_KV:
        items = _mock_storage.get(key, [])
        if stop == -1:
            return items[start:]
        return items[start:stop+1]
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{KV_REST_API_URL}/lrange/{key}/{start}/{stop}",
                headers={"Authorization": f"Bearer {KV_REST_API_TOKEN}"},
            )
            if response.status_code == 200:
                result = response.json()
                items = result.get("result", [])
                return [json.loads(item) for item in items]
            return []
    except Exception as e:
        logger.error("Failed to lrange KV value", key=key, error=str(e))
        return []


async def log_query(
    request_id: str,
    user_id: str,
    channel: str,
    query_text: str,
    response_topic: Optional[str] = None,
    confidence: Optional[float] = None,
    response_time_ms: int = 0,
    status: str = "success",
    session_id: Optional[str] = None,
) -> bool:
    """Log a query to analytics storage."""
    try:
        # Hash user ID for privacy
        from libs.common.settings import get_settings
        settings = get_settings()
        user_hash = hash_user_id(user_id, settings.secret_key)
        
        query_log = QueryLog(
            request_id=request_id,
            timestamp=time.time(),
            user_hash=user_hash,
            channel=channel,
            query_text=query_text[:1000],  # Truncate to prevent abuse
            response_topic=response_topic,
            confidence=confidence,
            response_time_ms=response_time_ms,
            status=status,
            session_id=session_id,
        )
        
        # Store in KV list with TTL (30 days)
        await _kv_lpush("queries", query_log.model_dump())
        
        logger.info(
            "Query logged",
            request_id=request_id,
            user_hash=user_hash,
            status=status,
            response_time_ms=response_time_ms,
        )
        
        return True
        
    except Exception as e:
        logger.error("Failed to log query", request_id=request_id, error=str(e))
        return False


async def save_feedback(
    request_id: str,
    user_id: str,
    rating: int,
    comment: Optional[str] = None,
) -> bool:
    """Save user feedback."""
    try:
        # Hash user ID for privacy
        from libs.common.settings import get_settings
        settings = get_settings()
        user_hash = hash_user_id(user_id, settings.secret_key)
        
        feedback = FeedbackEntry(
            request_id=request_id,
            timestamp=time.time(),
            user_hash=user_hash,
            rating=rating,
            comment=comment[:500] if comment else None,  # Truncate comment
        )
        
        # Store in KV list
        await _kv_lpush("feedback", feedback.model_dump())
        
        logger.info(
            "Feedback saved",
            request_id=request_id,
            user_hash=user_hash,
            rating=rating,
        )
        
        return True
        
    except Exception as e:
        logger.error("Failed to save feedback", request_id=request_id, error=str(e))
        return False


async def get_analytics_summary(hours: int = 24) -> AnalyticsSummary:
    """Get analytics summary for the specified time period."""
    try:
        # Get recent queries (last 1000 or so)
        queries_data = await _kv_lrange("queries", 0, 999)
        feedback_data = await _kv_lrange("feedback", 0, 999)
        
        # Filter by time period
        cutoff_time = time.time() - (hours * 3600)
        recent_queries = [
            q for q in queries_data 
            if q.get("timestamp", 0) >= cutoff_time
        ]
        
        # Calculate statistics
        total_queries = len(recent_queries)
        unique_users = len(set(q.get("user_hash") for q in recent_queries))
        
        # Average response time
        response_times = [q.get("response_time_ms", 0) for q in recent_queries]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Success rate
        successful_queries = [q for q in recent_queries if q.get("status") == "success"]
        success_rate = len(successful_queries) / total_queries if total_queries > 0 else 0
        
        # Top topics
        topic_counts = {}
        for query in successful_queries:
            topic = query.get("response_topic")
            if topic:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        top_topics = [
            {"topic": topic, "count": count}
            for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # Feedback statistics
        recent_feedback = [
            f for f in feedback_data 
            if f.get("timestamp", 0) >= cutoff_time
        ]
        
        feedback_stats = {
            "positive": len([f for f in recent_feedback if f.get("rating") == 1]),
            "neutral": len([f for f in recent_feedback if f.get("rating") == 0]),
            "negative": len([f for f in recent_feedback if f.get("rating") == -1]),
        }
        
        return AnalyticsSummary(
            total_queries=total_queries,
            unique_users=unique_users,
            avg_response_time_ms=avg_response_time,
            success_rate=success_rate,
            top_topics=top_topics,
            feedback_stats=feedback_stats,
            time_period=f"Last {hours} hours",
        )
        
    except Exception as e:
        logger.error("Failed to get analytics summary", error=str(e))
        return AnalyticsSummary(
            total_queries=0,
            unique_users=0,
            avg_response_time_ms=0.0,
            success_rate=0.0,
            top_topics=[],
            feedback_stats={"positive": 0, "neutral": 0, "negative": 0},
            time_period=f"Last {hours} hours",
        )


async def get_common_queries(limit: int = 20) -> List[Dict[str, Any]]:
    """Get common queries that didn't match any responses."""
    try:
        # Get recent queries
        queries_data = await _kv_lrange("queries", 0, 999)
        
        # Filter unmatched queries
        unmatched_queries = [
            q for q in queries_data 
            if q.get("status") in ["no_match", "error"]
        ]
        
        # Count occurrences
        query_counts = {}
        for query in unmatched_queries:
            text = query.get("query_text", "").lower().strip()
            if text and len(text) > 3:  # Filter out very short queries
                query_counts[text] = query_counts.get(text, 0) + 1
        
        # Return top queries
        common_queries = [
            {"query": query, "count": count}
            for query, count in sorted(query_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        ]
        
        return common_queries
        
    except Exception as e:
        logger.error("Failed to get common queries", error=str(e))
        return []