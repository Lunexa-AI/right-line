import pytest
from unittest.mock import AsyncMock, patch
from api.composer import compose_legal_answer, ComposedAnswer

@pytest.fixture
def mock_retrieval_results():
    return [
        {
            'text': 'The minimum wage is $10 per hour.',
            'title': 'Labor Law',
            'source_url': 'http://example.com/labor_law'
        },
        {
            'text': 'Overtime is 1.5 times the regular rate.',
            'title': 'Labor Law',
            'source_url': 'http://example.com/labor_law'
        }
    ]

@pytest.mark.asyncio
@patch('api.composer.ChatOpenAI')
async def test_compose_legal_answer_with_openai_success(mock_chat_openai, mock_retrieval_results):
    """
    Tests that compose_legal_answer successfully generates a response using OpenAI when enabled.
    """
    # Arrange
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = '{"tldr": "The minimum wage is $10/hour.", "key_points": ["Minimum wage is $10.", "Overtime is 1.5x."], "suggestions": ["Check local regulations."]}'
    mock_chat_openai.return_value = mock_llm
    
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
    assert result.confidence > 0.5
    assert len(result.citations) == 1
    mock_chat_openai.assert_called_once()
    mock_llm.ainvoke.assert_called_once()

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
@patch('api.composer.ChatOpenAI')
async def test_compose_legal_answer_openai_failure(mock_chat_openai, mock_retrieval_results):
    """
    Tests that compose_legal_answer falls back to the simple method if the OpenAI call fails.
    """
    # Arrange
    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = Exception("OpenAI API Error")
    mock_chat_openai.return_value = mock_llm
    
    # Act
    result = await compose_legal_answer(
        results=mock_retrieval_results,
        query="What is the minimum wage?",
        confidence=0.9,
        use_openai=True
    )
    
    # Assert
    assert isinstance(result, ComposedAnswer)
    assert "Based on the retrieved documents" in result.tldr # Fallback tldr
    assert len(result.key_points) == 2
    assert result.source == "retrieval_fallback"
    mock_chat_openai.assert_called_once()
    mock_llm.ainvoke.assert_called_once()
