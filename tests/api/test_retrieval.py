import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from api.tools.retrieval_engine import search_legal_documents, RetrievalResult

@pytest.mark.asyncio
@patch('api.tools.retrieval_engine.RetrievalEngine')
async def test_search_legal_documents_success(mock_engine_class):
    """
    Tests that search_legal_documents returns results when the query is valid.
    """
    # Arrange
    mock_engine = MagicMock()
    mock_engine.retrieve = AsyncMock()
    mock_engine_class.return_value.__aenter__.return_value = mock_engine
    
    mock_results = [
        RetrievalResult(
            chunk_id="chunk1",
            chunk_text="Test document content",
            doc_id="doc1",
            metadata={'title': 'Test Document', 'source_url': 'http://example.com'},
            score=0.9,
            source="vector"
        )
    ]
    
    mock_engine.retrieve.return_value = mock_results
    mock_engine.calculate_confidence.return_value = 0.85
    
    # Act
    results, confidence = await search_legal_documents('test query')
    
    # Assert
    assert len(results) == 1
    assert confidence == 0.85
    assert results[0].metadata['title'] == 'Test Document'
    mock_engine.retrieve.assert_called_once()
    mock_engine.calculate_confidence.assert_called_once_with(mock_results)


@pytest.mark.asyncio
@patch('api.tools.retrieval_engine.RetrievalEngine')
async def test_search_legal_documents_no_results(mock_engine_class):
    """
    Tests that search_legal_documents returns an empty list when no results are found.
    """
    # Arrange
    mock_engine = MagicMock()
    mock_engine.retrieve = AsyncMock()
    mock_engine_class.return_value.__aenter__.return_value = mock_engine
    
    mock_engine.retrieve.return_value = []
    mock_engine.calculate_confidence.return_value = 0.0
    
    # Act
    results, confidence = await search_legal_documents('unrelated query')
    
    # Assert
    assert len(results) == 0
    assert confidence == 0.0

@pytest.mark.asyncio
@patch('api.tools.retrieval_engine.RetrievalEngine')
async def test_search_legal_documents_engine_error(mock_engine_class):
    """
    Tests that search_legal_documents raises an exception when the engine fails.
    """
    # Arrange
    mock_engine = MagicMock()
    mock_engine.retrieve = AsyncMock()
    mock_engine_class.return_value.__aenter__.return_value = mock_engine
    mock_engine.retrieve.side_effect = Exception("Engine error")
    
    # Act & Assert
    with pytest.raises(Exception, match="Engine error"):
        await search_legal_documents('any query')

@pytest.mark.asyncio
@patch('api.tools.retrieval_engine.RetrievalEngine')
async def test_search_legal_documents_context_manager_error(mock_engine_class):
    """
    Tests that search_legal_documents handles context manager initialization errors.
    """
    # Arrange
    mock_engine_class.return_value.__aenter__.side_effect = Exception("Context manager error")
    
    # Act & Assert
    with pytest.raises(Exception, match="Context manager error"):
        await search_legal_documents('any query')
