"""Functions for managing user conversation sessions in Firestore."""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Literal

from google.cloud.firestore_v1.async_client import AsyncClient
from google.cloud.firestore_v1.base_query import FieldFilter

from libs.models.firestore import FirestoreMessage

async def add_message_to_session(
    client: AsyncClient,
    user_id: str,
    session_id: str,
    role: Literal["user", "assistant"],
    content: str,
) -> None:
    """Adds a new message to a specific session in Firestore.

    Args:
        client: The Firestore client.
        user_id: The UID of the user.
        session_id: The ID of the session.
        role: The role of the message sender ('user' or 'assistant').
        content: The text content of the message.
    """
    message_id = str(uuid.uuid4())
    message = FirestoreMessage(
        message_id=message_id,
        session_id=session_id,
        user_id=user_id,
        role=role,
        content=content,
        timestamp=datetime.utcnow()
    )

    doc_ref = client.collection(f"users/{user_id}/sessions/{session_id}/messages").document(message_id)
    await doc_ref.set(message.model_dump())

async def get_session_history(
    client: AsyncClient, user_id: str, session_id: str, limit: int = 20
) -> List[Dict[str, Any]]:
    """Fetches the last N messages from a session.

    Args:
        client: The Firestore client.
        user_id: The UID of the user.
        session_id: The ID of the session.
        limit: The maximum number of messages to retrieve.

    Returns:
        A list of messages, ordered from oldest to newest.
    """
    collection_ref = client.collection(f"users/{user_id}/sessions/{session_id}/messages")
    
    # Firestore doesn't directly support `order_by` with `limit_to_last`,
    # so we order by timestamp descending and take the top N, then reverse.
    query = collection_ref.order_by("timestamp", direction="DESCENDING").limit(limit)
    
    docs = [doc async for doc in await query.stream()]
    
    history = [doc.to_dict() for doc in docs]
    
    # Reverse the list to have messages in chronological order (oldest first)
    return history[::-1]
