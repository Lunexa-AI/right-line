"""Functions for managing user profiles in Firestore."""

from google.cloud.firestore_v1.async_client import AsyncClient
from libs.models.firestore import FirestoreUser

async def get_user_profile(client: AsyncClient, uid: str) -> FirestoreUser | None:
    """Retrieves a user profile document from Firestore.

    Args:
        client: The asynchronous Firestore client.
        uid: The user's unique identifier.

    Returns:
        A FirestoreUser object if the profile exists, otherwise None.
    """
    doc_ref = client.collection("users").document(uid)
    snapshot = await doc_ref.get()

    if not snapshot.exists:
        return None

    return FirestoreUser(**snapshot.to_dict())

async def create_user_profile(client: AsyncClient, user_data: FirestoreUser) -> FirestoreUser:
    """Creates a new user profile document in Firestore.

    Args:
        client: The asynchronous Firestore client.
        user_data: The FirestoreUser object containing the profile data.
    
    Returns:
        The created FirestoreUser object.
    """
    doc_ref = client.collection("users").document(user_data.uid)
    await doc_ref.set(user_data.model_dump())
    return user_data
