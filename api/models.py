"""Pydantic models for RightLine API.

This module defines the request and response models used by the API endpoints.
All models follow the .cursorrules guidelines for validation and structure.
"""

from __future__ import annotations

import time
from typing import Literal, Any, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr


class QueryRequest(BaseModel):
    """Request model for a user query."""
    text: str = Field(..., max_length=1024, description="User query text", example="What is the minimum wage?")
    lang_hint: Optional[str] = Field("en", description="Language hint for the query (e.g., 'en', 'sn')", example="en")
    channel: str = Field("web", description="Channel the query originated from (e.g., 'web', 'whatsapp')", example="web")
    date_ctx: Optional[str] = Field(None, description="Date context for the query (e.g., '2023-10-26')", example="2023-10-26")

    @field_validator("text")
    @classmethod
    def text_must_not_be_empty(cls, v: str) -> str:
        """Validate that the query text is not empty."""
        if not v.strip():
            raise ValueError("Query text must not be empty")
        return v

    @field_validator("channel")
    @classmethod
    def channel_must_be_valid(cls, v: str) -> str:
        """Validate that the channel is one of the allowed values."""
        if v not in ["web", "whatsapp", "test"]:
            raise ValueError("Invalid channel specified")
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
        max_length=2000,  # Increased for comprehensive legal summaries
        description="Brief summary of the legal information",
        example="Minimum wage in Zimbabwe is USD $175 per month. Employers must pay this or higher amount.",
    )
    key_points: List[str] = Field(..., max_length=20, description="Key points summarizing the answer.", example=["The minimum wage is $1.50 per hour for domestic workers."])
    citations: List[Citation] = Field(..., description="List of citations used to generate the answer.")
    suggestions: List[str] = Field(..., max_length=5, description="Suggested follow-up questions.", example=["What are the working hours for domestic workers?"])
    confidence: float = Field(..., description="Confidence score of the answer (0.0 to 1.0).", example=0.95)
    source: str = Field(
        description="How the answer was composed",
        example="hybrid",
    )
    request_id: str | None = Field(
        default=None,
        description="Request identifier for tracking",
        example="req_1234567890",
    )
    processing_time_ms: Optional[int] = Field(None, description="Time taken to process the query in milliseconds.", example=543)
    full_analysis: Optional[str] = Field(None, max_length=10000, description="Full legal analysis with IRAC structure", example="Full IRAC legal analysis...")
    
    # Note: We allow empty key_points and suggestions arrays for production
    # Better to show nothing than generic placeholders


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


class SignupRequest(BaseModel):
    """Request model for user signup supporting both email/password and Google methods."""
    name: str = Field(..., min_length=1, max_length=100, description="User's full name")
    method: Literal["email", "google"] = Field(..., description="Signup method: 'email' for email/password, 'google' for Google OAuth")
    
    # Email/password signup fields
    email: Optional[EmailStr] = Field(None, description="User's email address (required for email signup)")
    password: Optional[str] = Field(None, min_length=6, description="User's password (required for email signup, minimum 6 characters)")
    
    # Google signup fields  
    firebase_token: Optional[str] = Field(None, description="Firebase ID token from Google signup (required for Google signup)")

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Validate that the name is not empty or just whitespace."""
        if not v.strip():
            raise ValueError("Name must not be empty")
        return v.strip()
    
    @model_validator(mode='after')
    def validate_method_requirements(self):
        """Validate that required fields are provided for each signup method."""
        if self.method == "email":
            if not self.email:
                raise ValueError("Email is required for email signup method")
            if not self.password:
                raise ValueError("Password is required for email signup method")
        elif self.method == "google":
            if not self.firebase_token:
                raise ValueError("Firebase token is required for Google signup method")
        return self


class SignupResponse(BaseModel):
    """Response model for successful user signup."""
    success: bool = Field(True, description="Whether the signup was successful")
    message: str = Field(description="Success message")
    user_id: str = Field(description="The Firebase UID of the created user")
    email: str = Field(description="The email address of the created user")


# Waitlist Models
class WaitlistRequest(BaseModel):
    """Request model for waitlist signup."""
    
    email: EmailStr = Field(
        ...,
        description="User's email address for waitlist signup",
        example="user@example.com"
    )
    source: str = Field(
        "web",
        max_length=50,
        description="Source channel where signup originated (e.g., 'web', 'referral', 'social')",
        example="web"
    )
    # Honeypot field for bot detection - should always be empty
    website: str | None = Field(
        None,
        max_length=0,
        description="Leave this field empty. Used for bot detection.",
        example="",
        exclude=True  # Don't include in OpenAPI docs
    )
    
    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """Normalize email to lowercase and strip whitespace."""
        # Additional sanitization beyond Pydantic EmailStr
        email_str = str(v).strip().lower()
        # Remove any potentially dangerous characters (though EmailStr should handle this)
        if len(email_str) > 254:  # RFC 5321 limit
            raise ValueError("Email address too long (max 254 characters)")
        return email_str
    
    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Validate and normalize the source field with enhanced sanitization."""
        # Strip and normalize
        normalized = v.strip().lower()
        if not normalized:
            return "web"  # Default fallback
            
        # Length validation
        if len(normalized) > 50:
            raise ValueError("Source must be 50 characters or less")
            
        # Character whitelist for source field (alphanumeric, dash, underscore)
        import re
        if not re.match(r'^[a-z0-9_-]+$', normalized):
            # If invalid characters, sanitize to web default
            return "web"
            
        return normalized
    
    @field_validator("website")
    @classmethod
    def validate_honeypot(cls, v: str | None) -> str | None:
        """Validate honeypot field - must be empty or None."""
        if v is not None and v.strip():
            raise ValueError("Bot detected: honeypot field should be empty")
        return None


class WaitlistResponse(BaseModel):
    """Response model for waitlist signup."""
    
    success: bool = Field(
        description="Whether the waitlist signup was successful",
        example=True
    )
    message: str = Field(
        description="Status message for the signup attempt",
        example="Successfully added to waitlist!"
    )
    already_subscribed: bool = Field(
        description="Whether the email was already in the waitlist (idempotent behavior)",
        example=False
    )
    waitlist_id: str | None = Field(
        None,
        description="Unique identifier for the waitlist entry (only for new signups)",
        example="550e8400-e29b-41d4-a716-446655440000"
    )

# ---------------------------------------------------------------------------
# V3 Canonical Data Models (PageIndex-aligned)
# ---------------------------------------------------------------------------

class ChunkV3(BaseModel):
    """Canonical chunk model used throughout the V3 pipeline.

    Notes
    -----
    * parent_doc_id is always identical to doc_id (one-parent-doc strategy)
    * tree_node_id maps to PageIndex node identifier (e.g. "0006")
    * section_path is a human-readable breadcrumb (e.g. "Part II > §3")
    """

    # Core identifiers
    doc_id: str = Field(..., description="Canonical document ID (parent)")
    chunk_id: str = Field(..., description="Unique chunk ID (hash)")
    tree_node_id: str | None = Field(
        None, description="PageIndex tree node identifier (4-digit zero-padded)"
    )

    # Content and location
    chunk_text: str = Field(..., description="Full text of the chunk")
    section_path: str | None = Field(
        None, description="Hierarchical path within the document (breadcrumb)"
    )
    start_char: int = Field(0, description="Start character position in document")
    end_char: int = Field(0, description="End character position in document")
    num_tokens: int = Field(0, description="Estimated token count")

    # Document metadata
    language: str = Field("eng", description="Document language code")
    doc_type: str = Field("act", description="Document type (act, si, ordinance, etc.)")
    date_context: str | None = Field(None, description="Date context for the content")
    source_url: str | None = Field(None, description="Source URL if available")
    nature: str | None = Field(None, description="Nature of the document")
    year: int | None = Field(None, description="Year of the document")
    chapter: str | None = Field(None, description="Chapter identifier")

    # Constitutional hierarchy metadata (critical for legal AI)
    authority_level: str | None = Field(None, description="Legal authority level (supreme, high, medium, low)")
    hierarchy_rank: int | None = Field(None, description="Hierarchical rank (1=Constitution, 2=Act, 3=SI, etc.)")
    binding_scope: str | None = Field(None, description="Binding scope (national, specific, limited)")
    subject_category: str | None = Field(None, description="Subject category (legislation, case_law, etc.)")

    # Entity extraction
    entities: dict[str, List[str]] | None = Field(
        default_factory=dict, description="Extracted entities (dates, statute_refs, etc.)"
    )

    # Additional metadata
    metadata: dict[str, Any] | None = Field(
        default_factory=dict, description="Additional metadata for the chunk"
    )

    # Deprecation shims (old code may still access these)
    @property
    def parent_doc_id(self) -> str:  # noqa: D401 – simple property shim
        """Alias maintained for V2 compatibility."""
        return self.doc_id


class ParentDocumentV3(BaseModel):
    """Full parent document stored in R2 (Markdown + tree)."""

    doc_id: str = Field(..., description="Canonical document ID")
    title: str | None = Field(None, description="Document title")
    chapter: str | None = Field(None, description="Chapter identifier")
    canonical_citation: str | None = Field(None, description="Official citation string")
    pageindex_markdown: str = Field(..., description="Full Markdown text from PageIndex")
    pageindex_tree: list[dict[str, Any]] | None = Field(
        None, description="Hierarchical tree nodes from PageIndex"
    )
    metadata: dict[str, Any] | None = Field(
        default_factory=dict, description="Additional metadata for the document"
    )


# Legacy re-exports (soft deprecation) ------------------------------------------------
# Importing code can transition gradually.
Chunk = ChunkV3  # type: ignore
ParentDocument = ParentDocumentV3  # type: ignore
