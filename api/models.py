"""Pydantic models for RightLine API.

This module defines the request and response models used by the API endpoints.
All models follow the .cursorrules guidelines for validation and structure.
"""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field, validator


class QueryRequest(BaseModel):
    """Request model for legal query endpoint.
    
    Attributes:
        text: The legal question or query text (3-1000 characters)
        lang_hint: Optional language hint for response (en/sn/nd)
        date_ctx: Optional date context for temporal queries (ISO format)
        channel: Channel identifier (web/whatsapp/telegram)
    """
    
    text: str = Field(
        min_length=3,
        max_length=1000,
        description="Legal question or query text",
        example="What is the minimum wage in Zimbabwe?",
    )
    lang_hint: Literal["en", "sn", "nd"] | None = Field(
        default=None,
        description="Language hint for response (en=English, sn=Shona, nd=Ndebele)",
        example="en",
    )
    date_ctx: str | None = Field(
        default=None,
        description="Date context for temporal queries (ISO format)",
        example="2024-01-01",
    )
    channel: str = Field(
        default="web",
        max_length=16,
        description="Channel identifier",
        example="web",
    )
    
    @validator("text")
    def validate_text(cls, v: str) -> str:
        """Validate and clean query text."""
        # Strip whitespace and control characters
        cleaned = "".join(char for char in v.strip() if ord(char) >= 32)
        if len(cleaned) < 3:
            raise ValueError("Query text must be at least 3 characters long")
        return cleaned
    
    @validator("channel")
    def validate_channel(cls, v: str) -> str:
        """Validate channel identifier."""
        allowed_channels = {"web", "whatsapp", "telegram", "api"}
        if v not in allowed_channels:
            raise ValueError(f"Channel must be one of: {', '.join(allowed_channels)}")
        return v


class Citation(BaseModel):
    """Citation model for legal sources.
    
    Attributes:
        title: Title of the legal document
        url: URL to the source document
        page: Optional page number
        sha: Optional content hash for verification
    """
    
    title: str = Field(
        description="Title of the legal document",
        example="Labour Act [Chapter 28:01]",
    )
    url: str = Field(
        description="URL to the source document",
        example="https://veritas.org.zw/labour-act",
    )
    page: int | None = Field(
        default=None,
        description="Page number in the document",
        example=15,
    )
    sha: str | None = Field(
        default=None,
        description="Content hash for verification",
        example="abc123def456",
    )


class SectionRef(BaseModel):
    """Reference to a specific legal section.
    
    Attributes:
        act: Name of the Act or legal document
        chapter: Chapter identifier
        section: Section number or identifier
        version: Optional version identifier
    """
    
    act: str = Field(
        description="Name of the Act or legal document",
        example="Labour Act",
    )
    chapter: str = Field(
        description="Chapter identifier",
        example="28:01",
    )
    section: str = Field(
        description="Section number or identifier",
        example="12A",
    )
    version: str | None = Field(
        default=None,
        description="Version identifier",
        example="2024-01-01",
    )


class QueryResponse(BaseModel):
    """Response model for legal query endpoint (New Serverless Format).
    
    Attributes:
        tldr: Brief summary (≤220 chars)
        key_points: 3-5 key points, ≤25 words each
        citations: List of source citations
        suggestions: 2-3 follow-up questions
        confidence: Confidence score (0.0-1.0)
        source: How the answer was composed (extractive/openai/hybrid)
        request_id: Request identifier for tracking
        processing_time_ms: Processing time in milliseconds
    """
    
    tldr: str = Field(
        max_length=220,
        description="Brief summary of the legal information",
        example="Minimum wage in Zimbabwe is USD $175 per month. Employers must pay this or higher amount.",
    )
    key_points: list[str] = Field(
        max_items=5,
        description="3-5 key points, each ≤25 words",
        example=[
            "Current minimum wage is USD $175 per month for all sectors",
            "Employers cannot pay below this statutory minimum",
            "Violations result in fines up to USD $500"
        ],
    )
    citations: list[Citation] = Field(
        description="List of source citations",
        example=[],
    )
    suggestions: list[str] = Field(
        max_items=3,
        description="2-3 follow-up questions",
        example=[
            "How are overtime payments calculated?",
            "What are the penalties for late wage payments?"
        ],
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the response",
        example=0.85,
    )
    source: str = Field(
        description="How the answer was composed",
        example="hybrid",
    )
    request_id: str | None = Field(
        default=None,
        description="Request identifier for tracking",
        example="req_1234567890",
    )
    processing_time_ms: float | None = Field(
        default=None,
        description="Processing time in milliseconds",
        example=150.5,
    )
    
    @validator("key_points")
    def validate_key_points(cls, v: list[str]) -> list[str]:
        """Validate key points format and length."""
        if len(v) < 3:
            # Add default if not enough points
            defaults = ["Information available in legal documents", "Consult qualified legal counsel for advice"]
            v.extend(defaults[:3-len(v)])
        
        # Truncate points that are too long
        for i, point in enumerate(v):
            words = point.split()
            if len(words) > 25:
                v[i] = ' '.join(words[:25]) + '...'
        
        return v[:5]  # Limit to 5 points
    
    @validator("suggestions")
    def validate_suggestions(cls, v: list[str]) -> list[str]:
        """Validate suggestions format."""
        if len(v) < 2:
            # Add default suggestions if not enough
            defaults = [
                "What are the key employment rights in Zimbabwe?",
                "How do I file a complaint with labour authorities?"
            ]
            v.extend(defaults[:2-len(v)])
        
        return v[:3]  # Limit to 3 suggestions


class HealthResponse(BaseModel):
    """Response model for health check endpoints.
    
    Attributes:
        status: Health status (healthy/unhealthy/ready/not_ready)
        service: Service name
        version: Service version
        timestamp: Unix timestamp
        details: Optional additional details
    """
    
    status: Literal["healthy", "unhealthy", "ready", "not_ready"] = Field(
        description="Health status",
        example="healthy",
    )
    service: str = Field(
        description="Service name",
        example="api",
    )
    version: str = Field(
        description="Service version",
        example="0.1.0",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Unix timestamp",
        example=1703097600.0,
    )
    details: dict[str, str] | None = Field(
        default=None,
        description="Optional additional details",
        example={"database": "connected", "redis": "connected"},
    )


class ErrorResponse(BaseModel):
    """Standard error response model.
    
    Attributes:
        error: Error code
        message: Human-readable error message
        details: Optional error details
        request_id: Request identifier for tracking
    """
    
    error: str = Field(
        description="Error code",
        example="VALIDATION_ERROR",
    )
    message: str = Field(
        description="Human-readable error message",
        example="Invalid input provided",
    )
    details: dict[str, str] | None = Field(
        default=None,
        description="Optional error details",
        example={"field": "text", "issue": "too_short"},
    )
    request_id: str | None = Field(
        default=None,
        description="Request identifier for tracking",
        example="req_1234567890",
    )


# Feedback Models
class FeedbackRequest(BaseModel):
    """Request model for submitting feedback."""
    
    request_id: str = Field(
        description="Request ID to provide feedback for",
        example="req_1234567890",
    )
    rating: int = Field(
        ge=-1,
        le=1,
        description="Rating: -1 (negative), 0 (neutral), 1 (positive)",
        example=1,
    )
    comment: str | None = Field(
        default=None,
        max_length=500,
        description="Optional feedback comment",
        example="Very helpful response!",
    )


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""
    
    success: bool = Field(description="Whether feedback was saved successfully")
    message: str = Field(description="Status message")
    

# Analytics Models
class AnalyticsResponse(BaseModel):
    """Response model for analytics summary."""
    
    total_queries: int = Field(description="Total number of queries")
    unique_users: int = Field(description="Number of unique users")
    avg_response_time_ms: float = Field(description="Average response time in milliseconds")
    success_rate: float = Field(ge=0, le=100, description="Percentage of successful queries")
    top_topics: list[tuple[str, int]] = Field(description="Most queried topics")
    feedback_stats: dict[str, int] = Field(description="Feedback statistics")
    time_period: str = Field(description="Time period for analytics")
    

class CommonQueriesResponse(BaseModel):
    """Response model for common unmatched queries."""
    
    queries: list[tuple[str, int]] = Field(
        description="List of (query_text, count) tuples",
        example=[("pension calculation", 5), ("overtime rules", 3)],
    )
    total: int = Field(description="Total number of unmatched queries")
