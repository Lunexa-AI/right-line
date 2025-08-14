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
    """Response model for legal query endpoint.
    
    Attributes:
        summary_3_lines: Three-line summary of the legal information
        section_ref: Reference to the relevant legal section
        citations: List of source citations
        confidence: Confidence score (0.0-1.0)
        related_sections: List of related section identifiers
        request_id: Request identifier for tracking
        processing_time_ms: Processing time in milliseconds
    """
    
    summary_3_lines: str = Field(
        max_length=400,
        description="Three-line summary of the legal information",
        example="The minimum wage in Zimbabwe is set by statutory instrument.\nIt varies by sector and is reviewed periodically.\nEmployers must pay at least the prescribed minimum wage.",
    )
    section_ref: SectionRef = Field(
        description="Reference to the relevant legal section",
    )
    citations: list[Citation] = Field(
        description="List of source citations",
        example=[],
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the response",
        example=0.85,
    )
    related_sections: list[str] = Field(
        default_factory=list,
        description="List of related section identifiers",
        example=["12B", "13A"],
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
    
    @validator("summary_3_lines")
    def validate_summary(cls, v: str) -> str:
        """Validate summary format and length."""
        lines = v.strip().split('\n')
        if len(lines) > 3:
            # Truncate to 3 lines if more are provided
            v = '\n'.join(lines[:3])
        
        # Ensure each line is not too long
        max_line_length = 120
        lines = v.split('\n')
        truncated_lines = []
        for line in lines:
            if len(line) > max_line_length:
                truncated_lines.append(line[:max_line_length-3] + "...")
            else:
                truncated_lines.append(line)
        
        return '\n'.join(truncated_lines)


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
