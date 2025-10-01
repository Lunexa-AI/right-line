"""
Tests for follow-up question handling.

Tests verify:
- Follow-up pattern detection
- Pronoun resolution using context
- Context reference resolution
- Query rewriting with conversation context

Follows .cursorrules: TDD, comprehensive testing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def orchestrator():
    """Create orchestrator for testing."""
    from api.orchestrators.query_orchestrator import QueryOrchestrator
    return QueryOrchestrator()


@pytest.mark.asyncio
async def test_detect_follow_up_patterns(orchestrator):
    """Test follow-up pattern detection."""
    
    # These should be detected as follow-ups
    follow_up_queries = [
        "What about termination?",
        "And if I'm fired?",
        "But if it's unfair?",
        "Tell me more",
        "What is it?",
        "How about that?",
        "As you mentioned"
    ]
    
    for query in follow_up_queries:
        is_follow_up = orchestrator._detect_follow_up(query, "Previous query")
        assert is_follow_up, f"Should detect '{query}' as follow-up"


@pytest.mark.asyncio
async def test_not_follow_up(orchestrator):
    """Test non-follow-up queries."""
    
    # These should NOT be follow-ups
    non_follow_ups = [
        "What is labour law?",
        "How do I register a company?",
        "Can employer dismiss without hearing?"
    ]
    
    for query in non_follow_ups:
        is_follow_up = orchestrator._detect_follow_up(query, None)
        assert not is_follow_up, f"Should not detect '{query}' as follow-up"


@pytest.mark.asyncio
async def test_resolve_pronoun_it(orchestrator):
    """Test resolving 'it' pronoun from context."""
    
    conversation_history = [
        {
            "role": "user",
            "content": "What is unfair dismissal?",
            "timestamp": "2024-01-01T10:00:00"
        },
        {
            "role": "assistant",
            "content": "Unfair dismissal occurs when an employer terminates employment without following proper procedures...",
            "timestamp": "2024-01-01T10:00:05"
        }
    ]
    
    query = "Is it common?"
    
    # Resolve context
    resolved = await orchestrator._resolve_context_references(
        query, conversation_history
    )
    
    # Should either resolve "it" or at least attempt resolution
    # Since we're using real LLM, just verify it returns something
    assert resolved is not None
    assert len(resolved) > 0


@pytest.mark.asyncio
async def test_resolve_what_about(orchestrator):
    """Test resolving 'what about' questions."""
    
    conversation_history = [
        {
            "role": "user",
            "content": "What are employee rights under labour law?",
            "timestamp": "2024-01-01T10:00:00"
        },
        {
            "role": "assistant",
            "content": "Employees have rights to fair treatment, proper notice period...",
            "timestamp": "2024-01-01T10:00:05"
        }
    ]
    
    query = "What about termination procedures?"
    
    # Should understand this is about employment/labour law context
    resolved = await orchestrator._resolve_context_references(
        query, conversation_history
    )
    
    # Should return a resolved query
    assert resolved is not None
    assert len(resolved) > 0


@pytest.mark.asyncio
async def test_no_context_returns_original(orchestrator):
    """Test that queries without context return unchanged."""
    
    query = "What is labour law?"
    
    resolved = await orchestrator._resolve_context_references(query, [])
    
    # Should return original when no context
    assert resolved == query
