"""Pydantic models for Firestore collections.

These models define the structure of the documents stored in Firestore
and are used for data validation and serialization.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

class FirestoreUser(BaseModel):
    """Represents a user's profile in Firestore."""
    uid: str = Field(..., description="The user's unique Firebase UID.")
    email: str | None = Field(None, description="The user's email address.")
    name: str | None = Field(None, description="The user's full name.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of user creation.")
    long_term_summary: str | None = Field(None, description="AI-generated summary of user's long-term interests.")

class FirestoreSession(BaseModel):
    """Represents a single conversation session in Firestore."""
    session_id: str = Field(..., description="Unique identifier for the session.")
    user_id: str = Field(..., description="UID of the user who owns the session.")
    start_time: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the session start.")
    title: str | None = Field(None, description="A short, descriptive title for the session.")

class FirestoreMessage(BaseModel):
    """Represents a single message within a session in Firestore."""
    message_id: str = Field(..., description="Unique identifier for the message.")
    session_id: str = Field(..., description="The session this message belongs to.")
    user_id: str = Field(..., description="The user who sent the message (or is receiving it).")
    role: Literal["user", "assistant"] = Field(..., description="The role of the message sender.")
    content: str = Field(..., description="The text content of the message.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the message.")

class FirestoreFeedback(BaseModel):
    """Represents user feedback for a specific query response."""
    feedback_id: str | None = Field(None, description="Unique identifier for the feedback document.")
    request_id: str = Field(..., description="The request_id of the query this feedback is for.")
    user_id: str = Field(..., description="UID of the user providing feedback.")
    rating: int = Field(..., ge=-1, le=1, description="Rating: -1 (bad), 0 (neutral), 1 (good).")
    comment: str | None = Field(None, max_length=500, description="Optional user comment.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the feedback submission.")
