"""Functions for handling user feedback in Firestore."""

import uuid
from datetime import datetime

from google.cloud.firestore_v1.async_client import AsyncClient

from libs.models.firestore import FirestoreFeedback

async def save_feedback_to_firestore(
    client: AsyncClient,
    request_id: str,
    user_id: str,
    rating: int,
    comment: str | None,
) -> bool:
    """Saves user feedback to the 'feedback' collection in Firestore.

    Args:
        client: The asynchronous Firestore client.
        request_id: The ID of the request the feedback is for.
        user_id: The UID of the user providing the feedback.
        rating: The user's rating (-1, 0, or 1).
        comment: An optional text comment.

    Returns:
        True if the feedback was saved successfully, False otherwise.
    """
    try:
        feedback_id = str(uuid.uuid4())
        feedback = FirestoreFeedback(
            feedback_id=feedback_id,
            request_id=request_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
            timestamp=datetime.utcnow()
        )

        doc_ref = client.collection("feedback").document(feedback_id)
        await doc_ref.set(feedback.model_dump())
        return True
    except Exception:
        # In a real application, you'd want more specific logging here.
        return False
