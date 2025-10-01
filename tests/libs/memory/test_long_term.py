"""
Tests for long-term memory (user patterns and preferences).

Tests verify:
- Get user profile (creates default if not exists)
- Update profile after query
- Track legal interests and frequencies
- Detect expertise level
- Get personalization context

Follows .cursorrules: TDD, async testing, Firestore mocking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime


@pytest.fixture
def mock_firestore():
    """Create mock Firestore client."""
    from unittest.mock import AsyncMock
    
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_doc_ref = AsyncMock()  # Make doc_ref async
    
    # Setup chain: client.collection().document()
    mock_client.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc_ref
    
    return mock_client, mock_doc_ref


@pytest.fixture
async def long_term_memory(mock_firestore):
    """Create long-term memory instance with mocked Firestore."""
    from libs.memory.long_term import LongTermMemory
    
    mock_client, _ = mock_firestore
    memory = LongTermMemory(mock_client)
    
    return memory


@pytest.mark.asyncio
async def test_get_user_profile_creates_default(long_term_memory, mock_firestore):
    """Test that get_user_profile creates default profile if not exists."""
    
    _, mock_doc_ref = mock_firestore
    
    # Mock document doesn't exist
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_doc_ref.get.return_value = mock_doc
    
    # Get profile
    profile = await long_term_memory.get_user_profile("user_123")
    
    # Should return default profile
    assert profile["user_id"] == "user_123"
    assert profile["query_count"] == 0
    assert profile["expertise_level"] == "citizen"
    assert profile["legal_interests"] == []


@pytest.mark.asyncio
async def test_get_existing_user_profile(long_term_memory, mock_firestore):
    """Test retrieving existing user profile."""
    
    _, mock_doc_ref = mock_firestore
    
    # Mock existing profile
    existing_profile = {
        "user_id": "user_123",
        "query_count": 15,
        "expertise_level": "professional",
        "legal_interests": ["employment_law", "company_law"],
        "area_frequency": {"employment_law": 10, "company_law": 5}
    }
    
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = existing_profile
    mock_doc_ref.get.return_value = mock_doc
    
    # Get profile
    profile = await long_term_memory.get_user_profile("user_123")
    
    assert profile["query_count"] == 15
    assert profile["expertise_level"] == "professional"
    assert len(profile["legal_interests"]) == 2


@pytest.mark.asyncio
async def test_update_after_query(long_term_memory, mock_firestore):
    """Test updating profile after query."""
    
    _, mock_doc_ref = mock_firestore
    mock_doc_ref.update = AsyncMock()
    
    # Update after query
    await long_term_memory.update_after_query(
        user_id="user_123",
        query="What is labour law?",
        complexity="moderate",
        legal_areas=["employment_law"],
        user_type="professional"
    )
    
    # Verify update was called
    assert mock_doc_ref.update.called
    
    # Check update included query count increment
    update_dict = mock_doc_ref.update.call_args[0][0]
    assert "query_count" in str(update_dict) or "updated_at" in update_dict


@pytest.mark.asyncio
async def test_get_personalization_context(long_term_memory, mock_firestore):
    """Test getting personalization context for query processing."""
    
    _, mock_doc_ref = mock_firestore
    
    # Mock profile with data
    profile = {
        "user_id": "user_123",
        "query_count": 20,
        "expertise_level": "professional",
        "typical_complexity": "complex",
        "area_frequency": {
            "employment_law": 15,
            "company_law": 8,
            "constitutional_law": 3
        }
    }
    
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = profile
    mock_doc_ref.get.return_value = mock_doc
    
    # Get personalization context
    context = await long_term_memory.get_personalization_context("user_123")
    
    # Should extract key info
    assert context["expertise_level"] == "professional"
    assert context["typical_complexity"] == "complex"
    assert len(context["top_legal_interests"]) <= 5
    assert "employment_law" in context["top_legal_interests"]  # Most frequent
    assert context["is_returning_user"] is True  # query_count > 5


@pytest.mark.asyncio
async def test_expertise_detection_from_patterns(long_term_memory, mock_firestore):
    """Test that expertise level is detected from query patterns."""
    
    _, mock_doc_ref = mock_firestore
    
    # Mock new user profile
    profile = {
        "user_id": "user_456",
        "query_count": 3,
        "expertise_level": "citizen"
    }
    
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = profile
    mock_doc_ref.get.return_value = mock_doc
    
    context = await long_term_memory.get_personalization_context("user_456")
    
    assert context["is_returning_user"] is False  # query_count < 5


@pytest.mark.asyncio
async def test_top_interests_sorted_by_frequency(long_term_memory, mock_firestore):
    """Test that top interests are sorted by frequency."""
    
    _, mock_doc_ref = mock_firestore
    
    profile = {
        "user_id": "user_789",
        "query_count": 30,
        "area_frequency": {
            "employment_law": 15,
            "company_law": 8,
            "contract_law": 4,
            "property_law": 2,
            "criminal_law": 1
        }
    }
    
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = profile
    mock_doc_ref.get.return_value = mock_doc
    
    context = await long_term_memory.get_personalization_context("user_789")
    
    # Top interests should be sorted by frequency
    top_interests = context["top_legal_interests"]
    assert top_interests[0] == "employment_law"  # Most frequent
    assert top_interests[1] == "company_law"  # Second most
    assert len(top_interests) <= 5  # Max 5
