import pytest
from unittest.mock import MagicMock, AsyncMock

from libs.firestore.session import get_session_history, add_message_to_session

# Helper class to mock an async iterator, required for Firestore's `stream()`
class AsyncIterator:
    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration

@pytest.fixture
def mock_firestore_session_helpers():
    """
    Provides a structured set of mocks for Firestore session functions.
    Returns a dictionary with handles to the client and key method mocks.
    """
    # 1. Mock the final methods that are awaited
    mock_set = AsyncMock()
    
    mock_message_doc = MagicMock()
    mock_message_doc.to_dict.return_value = {"role": "user", "content": "Hello"}
    mock_stream = AsyncMock(return_value=AsyncIterator([mock_message_doc]))

    # 2. Build the chain of mocks leading to the final methods
    mock_query = MagicMock()
    mock_query.stream = mock_stream
    
    mock_doc_ref = MagicMock()
    mock_doc_ref.set = mock_set
    
    mock_collection_ref = MagicMock()
    mock_collection_ref.document.return_value = mock_doc_ref
    mock_collection_ref.order_by.return_value.limit.return_value = mock_query

    # 3. Mock the top-level client
    mock_client = MagicMock()
    mock_client.collection.return_value = mock_collection_ref

    return {
        "client": mock_client,
        "collection_mock": mock_collection_ref,
        "doc_mock": mock_doc_ref,
        "set_mock": mock_set,
        "stream_mock": mock_stream,
    }

@pytest.mark.asyncio
async def test_add_message_to_session(mock_firestore_session_helpers):
    """Tests that a message is correctly added using the explicit mock chain."""
    # Arrange
    client = mock_firestore_session_helpers["client"]
    set_mock = mock_firestore_session_helpers["set_mock"]
    collection_mock = mock_firestore_session_helpers["collection_mock"]

    # Act
    await add_message_to_session(
        client=client,
        user_id="test-user",
        session_id="test-session",
        role="user",
        content="This is a test message."
    )

    # Assert
    collection_mock.document.assert_called_once()
    assert set_mock.await_count == 1
    
    # Check the data passed to .set
    set_call_args = set_mock.call_args.args[0]
    assert set_call_args["role"] == "user"
    assert set_call_args["content"] == "This is a test message."

@pytest.mark.asyncio
async def test_get_session_history(mock_firestore_session_helpers):
    """Tests fetching history using the explicit mock chain."""
    # Arrange
    client = mock_firestore_session_helpers["client"]
    stream_mock = mock_firestore_session_helpers["stream_mock"]

    # Act
    history = await get_session_history(
        client=client,
        user_id="test-user",
        session_id="test-session"
    )

    # Assert
    assert stream_mock.await_count == 1
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
