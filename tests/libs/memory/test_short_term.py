"""
Tests for short-term memory (conversation context).

Tests verify:
- Add messages to session
- Retrieve context within token budget
- Sliding window (FIFO)
- TTL expiration (24 hours)
- Get last N exchanges

Follows .cursorrules: TDD, comprehensive coverage.
"""

import pytest
from datetime import datetime


@pytest.fixture
async def short_term_memory():
    """Create short-term memory instance with fresh fakeredis."""
    from libs.memory.short_term import ShortTermMemory
    from fakeredis import aioredis as fakeredis
    
    # Create fresh fakeredis for each test (avoids event loop issues)
    redis = fakeredis.FakeRedis(decode_responses=True)
    memory = ShortTermMemory(redis, max_messages=10)
    
    # Clear any existing data
    await redis.flushdb()
    
    yield memory
    
    # Cleanup
    await redis.flushdb()
    await redis.close()


@pytest.mark.asyncio
async def test_add_message(short_term_memory):
    """Test adding a message to session."""
    
    session_id = "test_session_1"
    
    await short_term_memory.add_message(
        session_id=session_id,
        role="user",
        content="What is labour law?",
        metadata={"intent": "rag_qa"}
    )
    
    # Verify message was stored
    messages = await short_term_memory.get_context(session_id)
    
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is labour law?"


@pytest.mark.asyncio
async def test_sliding_window(short_term_memory):
    """Test sliding window keeps only max_messages."""
    
    session_id = "test_session_2"
    
    # Add 15 messages (max is 10)
    for i in range(15):
        await short_term_memory.add_message(
            session_id=session_id,
            role="user",
            content=f"Message {i}"
        )
    
    # Should only keep last 10
    messages = await short_term_memory.get_context(session_id)
    
    assert len(messages) == 10, f"Should keep only 10 messages, got {len(messages)}"
    
    # Should be newest 10 (messages 5-14)
    assert messages[0]["content"] == "Message 5"  # Oldest kept
    assert messages[-1]["content"] == "Message 14"  # Newest


@pytest.mark.asyncio
async def test_get_context_token_budget(short_term_memory):
    """Test that get_context respects token budget."""
    
    session_id = "test_session_3"
    
    # Add messages with varying lengths
    await short_term_memory.add_message(session_id, "user", "Short query")
    await short_term_memory.add_message(session_id, "assistant", "A" * 2000)  # ~500 tokens
    await short_term_memory.add_message(session_id, "user", "Another query")
    await short_term_memory.add_message(session_id, "assistant", "B" * 2000)  # ~500 tokens
    
    # Get context with small budget
    messages = await short_term_memory.get_context(session_id, max_tokens=600)
    
    # Should return only messages that fit in budget
    # Newest messages should be prioritized
    total_chars = sum(len(m["content"]) for m in messages)
    estimated_tokens = total_chars // 4
    
    assert estimated_tokens <= 650, f"Should respect token budget, got ~{estimated_tokens} tokens"


@pytest.mark.asyncio
async def test_get_last_n_exchanges(short_term_memory):
    """Test getting last N query-response exchanges."""
    
    session_id = "test_session_4"
    
    # Add 3 exchanges
    for i in range(3):
        await short_term_memory.add_message(session_id, "user", f"Query {i}")
        await short_term_memory.add_message(session_id, "assistant", f"Response {i}")
    
    # Get last 2 exchanges
    exchanges = await short_term_memory.get_last_n_exchanges(session_id, n=2)
    
    assert len(exchanges) == 2
    assert exchanges[0]["user"]["content"] == "Query 1"
    assert exchanges[0]["assistant"]["content"] == "Response 1"
    assert exchanges[1]["user"]["content"] == "Query 2"
    assert exchanges[1]["assistant"]["content"] == "Response 2"


@pytest.mark.asyncio
async def test_ttl_set_correctly(short_term_memory):
    """Test that TTL is set to 24 hours."""
    
    session_id = "test_session_5"
    
    await short_term_memory.add_message(session_id, "user", "Test")
    
    # Check TTL in Redis
    key = f"session:{session_id}:messages"
    ttl = await short_term_memory.redis.ttl(key)
    
    # Should be ~24 hours (86400 seconds)
    assert 86300 < ttl <= 86400, f"TTL should be ~86400s, got {ttl}s"


@pytest.mark.asyncio
async def test_multiple_sessions_isolated(short_term_memory):
    """Test that different sessions are isolated."""
    
    await short_term_memory.add_message("session_A", "user", "Message A")
    await short_term_memory.add_message("session_B", "user", "Message B")
    
    messages_A = await short_term_memory.get_context("session_A")
    messages_B = await short_term_memory.get_context("session_B")
    
    assert len(messages_A) == 1
    assert len(messages_B) == 1
    assert messages_A[0]["content"] == "Message A"
    assert messages_B[0]["content"] == "Message B"


@pytest.mark.asyncio
async def test_metadata_preserved(short_term_memory):
    """Test that message metadata is preserved."""
    
    session_id = "test_session_6"
    
    metadata = {
        "intent": "rag_qa",
        "complexity": "moderate",
        "legal_areas": ["employment"]
    }
    
    await short_term_memory.add_message(
        session_id, "user", "Test", metadata=metadata
    )
    
    messages = await short_term_memory.get_context(session_id)
    
    assert messages[0]["metadata"] == metadata
