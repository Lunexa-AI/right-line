"""
Analytics and feedback collection for RightLine MVP.

This module provides lightweight query logging and feedback collection
using SQLite for persistence. Follows privacy-first principles with
HMAC-hashed user identifiers.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, Optional

import aiosqlite
import structlog
from pydantic import BaseModel, Field

from libs.common.settings import Settings

logger = structlog.get_logger(__name__)

# Database path - use local directory in development, /data in production
import os
if os.environ.get("RIGHTLINE_APP_ENV") == "production":
    DB_PATH = Path("/data/rightline_analytics.db")
else:
    DB_PATH = Path("./data/rightline_analytics.db")
    
# Create directory if it doesn't exist
try:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
except OSError:
    # Fallback to temp directory if /data is not writable
    import tempfile
    DB_PATH = Path(tempfile.gettempdir()) / "rightline_analytics.db"


class QueryLog(BaseModel):
    """Model for query log entries."""
    
    request_id: str
    timestamp: datetime
    user_hash: str
    channel: str
    query_text: str = Field(max_length=1000)
    response_topic: Optional[str] = None
    confidence: Optional[float] = None
    response_time_ms: int
    status: str  # success, error, no_match
    session_id: Optional[str] = None
    
    
class FeedbackEntry(BaseModel):
    """Model for user feedback."""
    
    id: Optional[int] = None
    request_id: str
    timestamp: datetime
    user_hash: str
    rating: int = Field(ge=-1, le=1)  # -1: negative, 0: neutral, 1: positive
    comment: Optional[str] = Field(default=None, max_length=500)
    

class AnalyticsSummary(BaseModel):
    """Summary statistics for analytics."""
    
    total_queries: int
    unique_users: int
    avg_response_time_ms: float
    success_rate: float
    top_topics: list[tuple[str, int]]
    feedback_stats: dict[str, int]
    time_period: str


def hash_user_id(user_id: str, secret: str) -> str:
    """
    Create HMAC hash of user ID for privacy.
    
    Args:
        user_id: Raw user identifier (phone, session ID, etc.)
        secret: Secret key for HMAC
        
    Returns:
        Hex-encoded HMAC hash
    """
    return hmac.new(
        secret.encode(),
        user_id.encode(),
        hashlib.sha256
    ).hexdigest()


@contextmanager
def get_db_connection() -> Iterator[sqlite3.Connection]:
    """Get synchronous database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@asynccontextmanager
async def get_async_db() -> AsyncIterator[aiosqlite.Connection]:
    """Get async database connection."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_database() -> None:
    """Initialize analytics database with tables."""
    async with get_async_db() as db:
        # Query logs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT UNIQUE NOT NULL,
                timestamp DATETIME NOT NULL,
                user_hash TEXT NOT NULL,
                channel TEXT NOT NULL,
                query_text TEXT NOT NULL,
                response_topic TEXT,
                confidence REAL,
                response_time_ms INTEGER NOT NULL,
                status TEXT NOT NULL,
                session_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Feedback table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                user_hash TEXT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES query_logs(request_id)
            )
        """)
        
        # Indexes for performance
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_logs_timestamp 
            ON query_logs(timestamp DESC)
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_logs_user_hash 
            ON query_logs(user_hash)
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_logs_status 
            ON query_logs(status)
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_request_id 
            ON feedback(request_id)
        """)
        
        await db.commit()
        logger.info("Analytics database initialized")


async def log_query(
    request_id: str,
    user_id: str,
    channel: str,
    query_text: str,
    response_topic: Optional[str],
    confidence: Optional[float],
    response_time_ms: int,
    status: str,
    session_id: Optional[str],
    settings: Settings
) -> None:
    """
    Log a query to the analytics database.
    
    Args:
        request_id: Unique request identifier
        user_id: Raw user identifier (will be hashed)
        channel: Channel (web, whatsapp, telegram)
        query_text: User's query text (truncated to 1000 chars)
        response_topic: Topic of the response (if matched)
        confidence: Confidence score of response
        response_time_ms: Response time in milliseconds
        status: Query status (success, error, no_match)
        session_id: Optional session identifier
        settings: Application settings
    """
    try:
        user_hash = hash_user_id(user_id, settings.secret_key)
        query_text = query_text[:1000]  # Truncate for safety
        
        async with get_async_db() as db:
            await db.execute("""
                INSERT INTO query_logs (
                    request_id, timestamp, user_hash, channel, query_text,
                    response_topic, confidence, response_time_ms, status, session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id,
                datetime.utcnow().isoformat(),
                user_hash,
                channel,
                query_text,
                response_topic,
                confidence,
                response_time_ms,
                status,
                session_id
            ))
            await db.commit()
            
    except Exception as e:
        # Don't fail the request if analytics fails
        logger.error("Failed to log query", error=str(e), request_id=request_id)


async def save_feedback(
    request_id: str,
    user_id: str,
    rating: int,
    comment: Optional[str],
    settings: Settings
) -> bool:
    """
    Save user feedback for a query.
    
    Args:
        request_id: Request ID to provide feedback for
        user_id: Raw user identifier (will be hashed)
        rating: Rating (-1: negative, 0: neutral, 1: positive)
        comment: Optional feedback comment
        settings: Application settings
        
    Returns:
        True if feedback was saved successfully
    """
    try:
        user_hash = hash_user_id(user_id, settings.secret_key)
        if comment:
            comment = comment[:500]  # Truncate for safety
            
        async with get_async_db() as db:
            # Check if request_id exists
            cursor = await db.execute(
                "SELECT 1 FROM query_logs WHERE request_id = ?",
                (request_id,)
            )
            if not await cursor.fetchone():
                logger.warning("Feedback for unknown request_id", request_id=request_id)
                return False
                
            await db.execute("""
                INSERT INTO feedback (
                    request_id, timestamp, user_hash, rating, comment
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                request_id,
                datetime.utcnow().isoformat(),
                user_hash,
                rating,
                comment
            ))
            await db.commit()
            
            logger.info(
                "Feedback saved",
                request_id=request_id,
                rating=rating,
                has_comment=bool(comment)
            )
            return True
            
    except Exception as e:
        logger.error("Failed to save feedback", error=str(e), request_id=request_id)
        return False


async def get_analytics_summary(
    hours: int = 24,
    settings: Optional[Settings] = None
) -> AnalyticsSummary:
    """
    Get analytics summary for the specified time period.
    
    Args:
        hours: Number of hours to look back
        settings: Application settings
        
    Returns:
        Analytics summary with statistics
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    
    async with get_async_db() as db:
        # Total queries and unique users
        cursor = await db.execute("""
            SELECT 
                COUNT(*) as total_queries,
                COUNT(DISTINCT user_hash) as unique_users,
                AVG(response_time_ms) as avg_response_time,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
            FROM query_logs
            WHERE timestamp >= ?
        """, (since.isoformat(),))
        
        row = await cursor.fetchone()
        total_queries = row["total_queries"] or 0
        unique_users = row["unique_users"] or 0
        avg_response_time = row["avg_response_time"] or 0
        success_rate = row["success_rate"] or 0
        
        # Top topics
        cursor = await db.execute("""
            SELECT response_topic, COUNT(*) as count
            FROM query_logs
            WHERE timestamp >= ? AND response_topic IS NOT NULL
            GROUP BY response_topic
            ORDER BY count DESC
            LIMIT 10
        """, (since.isoformat(),))
        
        top_topics = [(row["response_topic"], row["count"]) async for row in cursor]
        
        # Feedback statistics
        cursor = await db.execute("""
            SELECT 
                SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN rating = 0 THEN 1 ELSE 0 END) as neutral,
                SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) as negative
            FROM feedback
            WHERE timestamp >= ?
        """, (since.isoformat(),))
        
        row = await cursor.fetchone()
        feedback_stats = {
            "positive": row["positive"] or 0,
            "neutral": row["neutral"] or 0,
            "negative": row["negative"] or 0
        }
        
        return AnalyticsSummary(
            total_queries=total_queries,
            unique_users=unique_users,
            avg_response_time_ms=avg_response_time,
            success_rate=success_rate,
            top_topics=top_topics,
            feedback_stats=feedback_stats,
            time_period=f"Last {hours} hours"
        )


async def get_common_queries(
    limit: int = 20,
    min_count: int = 2
) -> list[tuple[str, int]]:
    """
    Get most common queries that appear multiple times.
    
    Args:
        limit: Maximum number of queries to return
        min_count: Minimum count to be included
        
    Returns:
        List of (query_text, count) tuples
    """
    async with get_async_db() as db:
        cursor = await db.execute("""
            SELECT query_text, COUNT(*) as count
            FROM query_logs
            WHERE status = 'no_match'
            GROUP BY LOWER(query_text)
            HAVING count >= ?
            ORDER BY count DESC
            LIMIT ?
        """, (min_count, limit))
        
        return [(row["query_text"], row["count"]) async for row in cursor]


async def cleanup_old_logs(days: int = 30) -> int:
    """
    Remove old query logs and feedback.
    
    Args:
        days: Number of days to keep
        
    Returns:
        Number of records deleted
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    async with get_async_db() as db:
        # Delete old feedback first (foreign key constraint)
        cursor = await db.execute("""
            DELETE FROM feedback
            WHERE timestamp < ?
        """, (cutoff.isoformat(),))
        
        feedback_deleted = cursor.rowcount
        
        # Delete old query logs
        cursor = await db.execute("""
            DELETE FROM query_logs
            WHERE timestamp < ?
        """, (cutoff.isoformat(),))
        
        logs_deleted = cursor.rowcount
        
        await db.commit()
        
        total_deleted = feedback_deleted + logs_deleted
        if total_deleted > 0:
            logger.info(
                "Cleaned up old analytics data",
                feedback_deleted=feedback_deleted,
                logs_deleted=logs_deleted
            )
        
        return total_deleted
