import pytest
from unittest.mock import MagicMock, AsyncMock

from libs.firestore.users import get_user_profile, create_user_profile
from libs.models.firestore import FirestoreUser

@pytest.fixture
def mock_firestore_user_helpers():
    """Provides explicit mocks for Firestore user profile functions."""
    # --- Mocks for get_user_profile ---
    mock_doc_snapshot = MagicMock()
    mock_doc_snapshot.exists = True
    mock_doc_snapshot.to_dict.return_value = {"uid": "existing-user", "name": "Existing User"}
    
    mock_get = AsyncMock(return_value=mock_doc_snapshot)
    
    # --- Mocks for create_user_profile ---
    mock_set = AsyncMock()

    # --- Mock Client and Document References ---
    mock_doc_ref = MagicMock()
    mock_doc_ref.get = mock_get
    mock_doc_ref.set = mock_set
    
    mock_collection_ref = MagicMock()
    mock_collection_ref.document.return_value = mock_doc_ref
    
    mock_client = MagicMock()
    mock_client.collection.return_value = mock_collection_ref

    return {
        "client": mock_client,
        "set_mock": mock_set,
        "get_mock": mock_get,
        "collection_mock": mock_collection_ref,
        "doc_mock": mock_doc_ref,
    }

@pytest.mark.asyncio
async def test_get_user_profile_found(mock_firestore_user_helpers):
    client = mock_firestore_user_helpers["client"]
    get_mock = mock_firestore_user_helpers["get_mock"]
    
    user = await get_user_profile(client, "existing-user")
    
    assert user is not None
    assert user.name == "Existing User"
    assert get_mock.await_count == 1

@pytest.mark.asyncio
async def test_create_user_profile(mock_firestore_user_helpers):
    client = mock_firestore_user_helpers["client"]
    set_mock = mock_firestore_user_helpers["set_mock"]
    user_data = FirestoreUser(uid="new-user", email="new@example.com", name="New User")
    
    await create_user_profile(client, user_data)
    
    assert set_mock.await_count == 1
    set_mock.assert_awaited_with(user_data.model_dump())
