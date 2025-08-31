import pytest
from unittest.mock import MagicMock, AsyncMock

# This import will fail until the file is created
from libs.firestore.feedback import save_feedback_to_firestore

@pytest.fixture
def mock_firestore_feedback_helpers():
    """Provides mocks for Firestore feedback functions."""
    mock_set = AsyncMock()
    mock_doc_ref = MagicMock()
    mock_doc_ref.set = mock_set
    mock_collection_ref = MagicMock()
    mock_collection_ref.document.return_value = mock_doc_ref
    mock_client = MagicMock()
    mock_client.collection.return_value = mock_collection_ref
    
    return {
        "client": mock_client,
        "set_mock": mock_set
    }

@pytest.mark.asyncio
async def test_save_feedback_to_firestore(mock_firestore_feedback_helpers):
    """Tests saving feedback to a Firestore collection."""
    # Arrange
    client = mock_firestore_feedback_helpers["client"]
    set_mock = mock_firestore_feedback_helpers["set_mock"]
    
    feedback_data = {
        "request_id": "test-req-123",
        "user_id": "test-user-456",
        "rating": 1,
        "comment": "Very helpful!"
    }
    
    # Act
    await save_feedback_to_firestore(client, **feedback_data)
    
    # Assert
    client.collection.assert_called_with("feedback")
    client.collection().document.assert_called_once()
    assert set_mock.await_count == 1
    
    set_call_args = set_mock.call_args.args[0]
    assert set_call_args["request_id"] == feedback_data["request_id"]
    assert set_call_args["rating"] == feedback_data["rating"]
    assert "timestamp" in set_call_args
