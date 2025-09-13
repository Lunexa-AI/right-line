import pytest
from unittest.mock import AsyncMock, patch
from api.composer import compose_legal_answer, ComposedAnswer
from api.retrieval import RetrievalResult

@pytest.fixture
def mock_retrieval_results():
    return [
        RetrievalResult(
            chunk_id="chunk1",
            chunk_text='The minimum wage is $10 per hour.',
            doc_id="doc1",
            metadata={'title': 'Labor Law', 'source_url': 'http://example.com/labor_law'},
            score=0.9,
            source="vector"
        ),
        RetrievalResult(
            chunk_id="chunk2",
            chunk_text='Overtime is 1.5 times the regular rate.',
            doc_id="doc1",
            metadata={'title': 'Labor Law', 'source_url': 'http://example.com/labor_law'},
            score=0.85,
            source="vector"
        )
    ]

@pytest.mark.asyncio
@patch('api.composer.httpx.AsyncClient')
async def test_compose_legal_answer_with_openai_success(mock_async_client_class, mock_retrieval_results):
    """
    Tests that compose_legal_answer successfully generates a response using OpenAI when enabled.
    """
    # Arrange
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"tldr": "The minimum wage is $10/hour.", "key_points": ["Minimum wage is $10.", "Overtime is 1.5x."], "suggestions": ["Check local regulations."]}'
            }
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }
    
    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(return_value=mock_response)
    
    # This is the key part: the __aenter__ of the class's return value should be the instance
    mock_async_client_class.return_value.__aenter__.return_value = mock_client_instance
    
    # Act
    result = await compose_legal_answer(
        results=mock_retrieval_results,
        query="What is the minimum wage?",
        confidence=0.9,
        use_openai=True
    )
    
    # Assert
    assert isinstance(result, ComposedAnswer)
    assert result.tldr == "The minimum wage is $10/hour."
    assert len(result.key_points) == 2
    assert "Check local regulations." in result.suggestions
    assert result.source == "hybrid"

@pytest.mark.asyncio
async def test_compose_legal_answer_without_openai(mock_retrieval_results):
    """
    Tests that compose_legal_answer generates a simple response without using OpenAI when disabled.
    """
    # Act
    result = await compose_legal_answer(
        results=mock_retrieval_results,
        query="What is the minimum wage?",
        confidence=0.9,
        use_openai=False
    )
    
    # Assert
    assert isinstance(result, ComposedAnswer)
    assert "Based on the retrieved documents" in result.tldr
    assert len(result.key_points) == 2
    assert result.key_points[0] == "The minimum wage is $10 per hour."
    assert result.confidence > 0.5
    assert len(result.citations) == 1
    
@pytest.mark.asyncio
async def test_compose_legal_answer_low_confidence(mock_retrieval_results):
    """
    Tests that compose_legal_answer returns a low-confidence response when retrieval confidence is low.
    """
    # Act
    result = await compose_legal_answer(
        results=mock_retrieval_results,
        query="What is the minimum wage?",
        confidence=0.1,  # Low confidence
        use_openai=True
    )
    
    # Assert
    assert isinstance(result, ComposedAnswer)
    assert "I'm not confident in the answer" in result.tldr
    assert result.confidence < 0.3
    assert len(result.citations) == 0

@pytest.mark.asyncio
async def test_compose_legal_answer_no_results():
    """
    Tests that compose_legal_answer returns a specific message when no documents are retrieved.
    """
    # Act
    result = await compose_legal_answer(
        results=[],  # No results
        query="What is the minimum wage?",
        confidence=0.0,
        use_openai=True
    )
    
    # Assert
    assert isinstance(result, ComposedAnswer)
    assert "I could not find any relevant legal documents" in result.tldr
    assert result.confidence == 0.1
    assert len(result.citations) == 0
    
@pytest.mark.asyncio
@patch('httpx.AsyncClient')
async def test_compose_legal_answer_openai_failure(mock_async_client, mock_retrieval_results):
    """
    Tests that compose_legal_answer falls back to the simple method if the OpenAI call fails.
    """
    # Arrange
    mock_async_client.return_value.__aenter__.return_value.post.side_effect = Exception("OpenAI API Error")
    
    # Act
    result = await compose_legal_answer(
        results=mock_retrieval_results,
        query="What is the minimum wage?",
        confidence=0.9,
        use_openai=True
    )
    
    # Assert
    assert isinstance(result, ComposedAnswer)
    assert result.source == "extractive" # Should fall back to extractive
