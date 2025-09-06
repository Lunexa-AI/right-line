"""Functions for managing waitlist entries in Firestore."""

import uuid
from datetime import datetime, UTC
from typing import List, Dict, Any, Tuple

from google.cloud.firestore_v1.async_client import AsyncClient
from google.cloud.firestore_v1.base_query import FieldFilter

from libs.models.firestore import WaitlistEntry


async def add_to_waitlist(
    client: AsyncClient,
    email: str,
    source: str = "web",
    metadata: Dict[str, str] | None = None,
) -> Tuple[bool, WaitlistEntry]:
    """Adds an email to the waitlist or returns existing entry (idempotent).

    Args:
        client: The asynchronous Firestore client.
        email: The user's email address (should be normalized/lowercase).
        source: The source channel (e.g., "web", "referral").
        metadata: Optional metadata dictionary (IP, user-agent, etc.).

    Returns:
        Tuple of (created: bool, entry: WaitlistEntry)
        - created=True if new entry was created
        - created=False if email already existed
    """
    try:
        # First check if email already exists
        existing_entry = await _get_waitlist_entry_by_email(client, email)
        if existing_entry:
            return (False, existing_entry)
        
        # Create new waitlist entry
        waitlist_id = str(uuid.uuid4())
        entry = WaitlistEntry(
            waitlist_id=waitlist_id,
            email=email,
            joined_at=datetime.now(UTC),
            source=source,
            metadata=metadata
        )

        # Save to Firestore
        doc_ref = client.collection("waitlist").document(waitlist_id)
        await doc_ref.set(entry.model_dump())
        
        return (True, entry)
        
    except Exception as e:
        # Re-raise with context for proper error handling upstream
        raise RuntimeError(f"Failed to add email to waitlist: {str(e)}") from e


async def check_email_exists(client: AsyncClient, email: str) -> bool:
    """Checks if an email already exists in the waitlist.

    Args:
        client: The asynchronous Firestore client.
        email: The email address to check (should be normalized/lowercase).

    Returns:
        True if email exists in waitlist, False otherwise.
    """
    try:
        existing_entry = await _get_waitlist_entry_by_email(client, email)
        return existing_entry is not None
    except Exception:
        # In case of errors, return False to avoid blocking signups
        return False


async def get_waitlist_stats(client: AsyncClient, limit: int = 10) -> Dict[str, Any]:
    """Retrieves waitlist statistics for admin purposes.

    Args:
        client: The asynchronous Firestore client.
        limit: Maximum number of recent entries to include (default: 10).

    Returns:
        Dictionary containing:
        - total_count: Total number of waitlist entries
        - recent_entries: List of recent entries (limited)
        - sources_breakdown: Count by source channel
        - latest_signup: Most recent signup timestamp
    """
    try:
        collection_ref = client.collection("waitlist")
        
        # Get total count
        total_docs = await collection_ref.count().get()
        total_count = total_docs[0][0].value if total_docs else 0
        
        # Get recent entries (ordered by joined_at desc)
        recent_query = collection_ref.order_by("joined_at", direction="DESCENDING").limit(limit)
        recent_docs = await recent_query.get()
        
        recent_entries = []
        sources_count = {}
        latest_signup = None
        
        for doc in recent_docs:
            data = doc.to_dict()
            recent_entries.append(data)
            
            # Count sources
            source = data.get("source", "unknown")
            sources_count[source] = sources_count.get(source, 0) + 1
            
            # Track latest signup
            if latest_signup is None or data.get("joined_at") > latest_signup:
                latest_signup = data.get("joined_at")
        
        return {
            "total_count": total_count,
            "recent_entries": recent_entries,
            "sources_breakdown": sources_count,
            "latest_signup": latest_signup,
        }
        
    except Exception as e:
        # Return empty stats on error to avoid breaking admin endpoints
        return {
            "total_count": 0,
            "recent_entries": [],
            "sources_breakdown": {},
            "latest_signup": None,
            "error": str(e),
        }


async def _get_waitlist_entry_by_email(
    client: AsyncClient, email: str
) -> WaitlistEntry | None:
    """Private helper to find waitlist entry by email.

    Args:
        client: The asynchronous Firestore client.
        email: The email address to search for.

    Returns:
        WaitlistEntry if found, None otherwise.
    """
    try:
        # Query by email field
        collection_ref = client.collection("waitlist")
        query = collection_ref.where(filter=FieldFilter("email", "==", email))
        docs = await query.get()
        
        if not docs:
            return None
            
        # Should only be one document per email
        doc = docs[0]
        return WaitlistEntry(**doc.to_dict())
        
    except Exception:
        # Return None on any error to maintain idempotent behavior
        return None


async def get_waitlist_entry_by_id(
    client: AsyncClient, waitlist_id: str
) -> WaitlistEntry | None:
    """Retrieves a specific waitlist entry by ID.

    Args:
        client: The asynchronous Firestore client.
        waitlist_id: The unique waitlist entry ID.

    Returns:
        WaitlistEntry if found, None otherwise.
    """
    try:
        doc_ref = client.collection("waitlist").document(waitlist_id)
        snapshot = await doc_ref.get()

        if not snapshot.exists:
            return None

        return WaitlistEntry(**snapshot.to_dict())
        
    except Exception:
        return None
