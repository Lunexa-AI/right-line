import pytest
from unittest.mock import AsyncMock, patch
from api.retrieval import search_legal_documents

@pytest.mark.asyncio
@patch('api.retrieval.get_milvus_connection')
@patch('api.retrieval.get_embeddings_model')
async def test_search_legal_documents_success(mock_get_embeddings, mock_get_milvus):
    """
    Tests that search_legal_documents returns results when the query is valid.
    """
    # Arrange
    mock_embeddings = AsyncMock()
    mock_embeddings.embed_query.return_value = [0.1] * 1536 
    mock_get_embeddings.return_value = mock_embeddings

    mock_milvus = AsyncMock()
    mock_milvus.search.return_value = [
        [
            {
                'entity': {
                    'title': 'Test Document',
                    'source_url': 'http://example.com',
                },
                'distance': 0.9
            }
        ]
    ]
    mock_get_milvus.return_value = mock_milvus
    
    # Act
    results, confidence = await search_legal_documents('test query')
    
    # Assert
    assert len(results) == 1
    assert confidence > 0
    assert results[0]['title'] == 'Test Document'
    mock_get_embeddings.assert_called_once()
    mock_get_milvus.assert_called_once()
    mock_embeddings.embed_query.assert_called_once_with('test query')
    mock_milvus.search.assert_called_once()


@pytest.mark.asyncio
@patch('api.retrieval.get_milvus_connection')
@patch('api.retrieval.get_embeddings_model')
async def test_search_legal_documents_no_results(mock_get_embeddings, mock_get_milvus):
    """
    Tests that search_legal_documents returns an empty list when no results are found.
    """
    # Arrange
    mock_embeddings = AsyncMock()
    mock_embeddings.embed_query.return_value = [0.1] * 1536
    mock_get_embeddings.return_value = mock_embeddings

    mock_milvus = AsyncMock()
    mock_milvus.search.return_value = [[]]
    mock_get_milvus.return_value = mock_milvus
    
    # Act
    results, confidence = await search_legal_documents('unrelated query')
    
    # Assert
    assert len(results) == 0
    assert confidence == 0.0

@pytest.mark.asyncio
@patch('api.retrieval.get_milvus_connection')
@patch('api.retrieval.get_embeddings_model', side_effect=Exception("Embedding model error"))
async def test_search_legal_documents_embedding_error(mock_get_embeddings, mock_get_milvus):
    """
    Tests that search_legal_documents raises an exception when the embedding model fails.
    """
    # Arrange
    mock_milvus = AsyncMock()
    mock_get_milvus.return_value = mock_milvus
    
    # Act & Assert
    with pytest.raises(Exception, match="Embedding model error"):
        await search_legal_documents('any query')

@pytest.mark.asyncio
@patch('api.retrieval.get_milvus_connection', side_effect=Exception("Milvus connection error"))
@patch('api.retrieval.get_embeddings_model')
async def test_search_legal_documents_milvus_error(mock_get_embeddings, mock_get_milvus):
    """
    Tests that search_legal_documents raises an exception when Milvus connection fails.
    """
    # Arrange
    mock_embeddings = AsyncMock()
    mock_embeddings.embed_query.return_value = [0.1] * 1536
    mock_get_embeddings.return_value = mock_embeddings
    
    # Act & Assert
    with pytest.raises(Exception, match="Milvus connection error"):
        await search_legal_documents('any query')
