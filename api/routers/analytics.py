from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status

from libs.common.settings import get_settings
from api.analytics import get_analytics_summary, get_common_queries
from api.models import AnalyticsResponse, CommonQueriesResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/v1/analytics", tags=["Analytics"])
async def get_analytics(
    hours: int = 24,
    api_key: str | None = None,
) -> AnalyticsResponse:
    """Get analytics summary.
    
    Returns query statistics for the specified time period.
    Protected endpoint - requires API key in production.
    
    Args:
        hours: Number of hours to look back (default: 24)
        api_key: Optional API key for authentication
        
    Returns:
        Analytics summary with statistics
        
    Example:
        ```bash
        curl http://localhost:8000/v1/analytics?hours=24
        ```
    """
    settings = get_settings()
    
    # Simple API key check for production
    if settings.app_env == "production" and api_key != settings.secret_key[:16]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    summary = await get_analytics_summary(hours=hours)
    
    return AnalyticsResponse(
        total_queries=summary.total_queries,
        unique_users=summary.unique_users,
        avg_response_time_ms=summary.avg_response_time_ms,
        success_rate=summary.success_rate,
        top_topics=summary.top_topics,
        feedback_stats=summary.feedback_stats,
        time_period=summary.time_period
    )


@router.get("/v1/analytics/common-queries", tags=["Analytics"])
async def get_common_unmatched_queries(
    limit: int = 20,
    api_key: str | None = None,
) -> CommonQueriesResponse:
    """Get common unmatched queries.
    
    Returns queries that frequently don't match any hardcoded responses.
    Useful for identifying gaps in coverage.
    
    Args:
        limit: Maximum number of queries to return
        api_key: Optional API key for authentication
        
    Returns:
        List of common unmatched queries with counts
        
    Example:
        ```bash
        curl http://localhost:8000/v1/analytics/common-queries?limit=10
        ```
    """
    settings = get_settings()
    
    # Simple API key check for production
    if settings.app_env == "production" and api_key != settings.secret_key[:16]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    queries = await get_common_queries(limit=limit)
    
    return CommonQueriesResponse(
        queries=queries,
        total=len(queries)
    )
