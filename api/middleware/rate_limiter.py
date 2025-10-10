"""
Simple in-memory rate limiter for API endpoints.

This implementation provides basic DDoS protection without requiring Redis
in development. For production, consider using slowapi or Redis-backed limiter.
"""

import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
import structlog

logger = structlog.get_logger(__name__)

# In-memory storage: {client_id: [(timestamp, request_count), ...]}
_request_history: Dict[str, list[Tuple[float, int]]] = defaultdict(list)


class RateLimiter:
    """Simple sliding window rate limiter."""
    
    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        enabled: bool = True
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            enabled: Whether rate limiting is enabled
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.enabled = enabled
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Try to get authenticated user ID first
        if hasattr(request.state, "user"):
            return f"user:{request.state.user.uid}"
        
        # Fall back to IP address
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Use first IP in X-Forwarded-For chain
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip:{client_ip}"
    
    def _clean_old_requests(self, client_id: str, current_time: float):
        """Remove requests older than the time window."""
        if client_id in _request_history:
            cutoff_time = current_time - self.window_seconds
            _request_history[client_id] = [
                (ts, count) for ts, count in _request_history[client_id]
                if ts > cutoff_time
            ]
    
    async def check_rate_limit(self, request: Request) -> None:
        """
        Check if request exceeds rate limit.
        
        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        if not self.enabled:
            return
        
        client_id = self._get_client_id(request)
        current_time = time.time()
        
        # Clean old requests
        self._clean_old_requests(client_id, current_time)
        
        # Count requests in current window
        request_count = sum(count for _, count in _request_history[client_id])
        
        if request_count >= self.max_requests:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                current_count=request_count,
                max_requests=self.max_requests,
                window_seconds=self.window_seconds
            )
            
            # Calculate retry-after
            if _request_history[client_id]:
                oldest_request_time = _request_history[client_id][0][0]
                retry_after = int(self.window_seconds - (current_time - oldest_request_time)) + 1
            else:
                retry_after = self.window_seconds
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Too many requests. Maximum {self.max_requests} requests per {self.window_seconds} seconds.",
                    "retry_after_seconds": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        # Record this request
        _request_history[client_id].append((current_time, 1))
        
        logger.debug(
            "Rate limit check passed",
            client_id=client_id,
            request_count=request_count + 1,
            max_requests=self.max_requests
        )


# Global rate limiter instances
query_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)  # 10 req/min
strict_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)   # 5 req/min for expensive ops

