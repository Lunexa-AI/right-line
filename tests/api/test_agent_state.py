#!/usr/bin/env python3
"""
Test suite for AgentState Pydantic model (Task 4.1)

Following TDD principles from .cursorrules, this test suite covers:
- AgentState model validation and serialization
- Field constraints and default values
- JSON round-trip serialization
- Schema evolution and versioning
- Size constraints (< 8KB typical)

Author: RightLine Team
"""

import json
import pytest
from typing import List
from pydantic import ValidationError

from api.schemas.agent_state import AgentState, Citation


class TestAgentStateBasicFunctionality:
    """Test basic AgentState model functionality."""
    
    def test_agent_state_minimal_creation(self):
        """Test creating AgentState with minimal required fields."""
        state = AgentState(
            trace_id="test-trace-123",
            user_id="user-456",
            session_id="session-789",
            raw_query="What is the minimum wage?"
        )
        
        assert state.trace_id == "test-trace-123"
        assert state.user_id == "user-456" 
        assert state.session_id == "session-789"
        assert state.raw_query == "What is the minimum wage?"
        assert state.state_version == "v1"
        
        # Check defaults
        assert state.session_history_ids == []
        assert state.user_profile_key is None
        assert state.jurisdiction is None
        assert state.date_context is None
        assert state.intent is None
        assert state.rewritten_query is None
        assert state.sub_questions == []
        assert state.hypothetical_docs == []
        assert state.retrieval_strategy is None
        assert state.candidate_chunk_ids == []
        assert state.reranked_chunk_ids == []
        assert state.parent_doc_keys == []
        assert state.synthesis_prompt_key is None
        assert state.final_answer is None
        assert state.cited_sources == []
        assert state.safety_flags == {}
    
    def test_agent_state_full_creation(self):
        """Test creating AgentState with all fields populated."""
        citations = [
            Citation(
                doc_key="labour_act_2023.json",
                page=5,
                snippet_range=(100, 200),
                confidence=0.95
            )
        ]
        
        state = AgentState(
            trace_id="test-trace-456",
            user_id="user-789",
            session_id="session-012",
            raw_query="What are employment rights?",
            session_history_ids=["hist1", "hist2"],
            user_profile_key="profile_key_123",
            jurisdiction="ZW",
            date_context="2023-01-01",
            intent="rag_qa",
            rewritten_query="Employment rights and obligations in Zimbabwe",
            sub_questions=["What are worker rights?", "What are employer obligations?"],
            hypothetical_docs=["Document about employment rights", "Guide to labor law"],
            retrieval_strategy="hybrid",
            candidate_chunk_ids=["chunk1", "chunk2", "chunk3"],
            reranked_chunk_ids=["chunk2", "chunk1"],
            parent_doc_keys=["doc1.json", "doc2.json"],
            synthesis_prompt_key="employment_synthesis_v1",
            final_answer="Employment rights in Zimbabwe include...",
            cited_sources=citations,
            safety_flags={"content_safe": True, "jurisdiction_valid": True}
        )
        
        assert len(state.session_history_ids) == 2
        assert state.jurisdiction == "ZW"
        assert len(state.sub_questions) == 2
        assert len(state.hypothetical_docs) == 2
        assert len(state.candidate_chunk_ids) == 3
        assert len(state.reranked_chunk_ids) == 2
        assert len(state.cited_sources) == 1
        assert state.cited_sources[0].doc_key == "labour_act_2023.json"
        assert state.cited_sources[0].confidence == 0.95
        assert state.safety_flags["content_safe"] is True
    
    def test_agent_state_json_serialization(self):
        """Test JSON round-trip serialization."""
        original_state = AgentState(
            trace_id="json-test-123",
            user_id="user-json",
            session_id="session-json",
            raw_query="Test JSON serialization",
            sub_questions=["Question 1", "Question 2"],
            candidate_chunk_ids=["chunk1", "chunk2"],
            safety_flags={"test": True}
        )
        
        # Serialize to JSON
        json_str = original_state.model_dump_json()
        json_data = json.loads(json_str)
        
        # Verify JSON structure
        assert json_data["trace_id"] == "json-test-123"
        assert json_data["state_version"] == "v1"
        assert len(json_data["sub_questions"]) == 2
        assert json_data["safety_flags"]["test"] is True
        
        # Deserialize back
        restored_state = AgentState.model_validate(json_data)
        
        # Verify round-trip
        assert restored_state.trace_id == original_state.trace_id
        assert restored_state.sub_questions == original_state.sub_questions
        assert restored_state.safety_flags == original_state.safety_flags
    
    def test_agent_state_size_constraint(self):
        """Test that typical AgentState is under 8KB."""
        # Create a realistic state with substantial content
        large_state = AgentState(
            trace_id="size-test-" + "x" * 50,
            user_id="user-" + "y" * 50,
            session_id="session-" + "z" * 50,
            raw_query="What are the detailed employment regulations in Zimbabwe?" * 5,
            session_history_ids=[f"hist_{i}" for i in range(10)],
            rewritten_query="Detailed employment regulations, worker rights, employer obligations" * 3,
            sub_questions=[f"Question {i} about employment law details" for i in range(3)],
            hypothetical_docs=[f"Hypothetical document {i} about labor regulations" for i in range(5)],
            candidate_chunk_ids=[f"chunk_{i}" for i in range(20)],
            reranked_chunk_ids=[f"chunk_{i}" for i in range(15)],
            parent_doc_keys=[f"doc_{i}.json" for i in range(10)],
            final_answer="A comprehensive answer about employment rights and regulations that includes multiple paragraphs of detailed information about worker protections, employer obligations, and legal frameworks." * 3,
            cited_sources=[
                Citation(doc_key=f"doc_{i}.json", page=i+1, confidence=0.9) 
                for i in range(5)
            ],
            safety_flags={f"flag_{i}": True for i in range(10)}
        )
        
        json_str = large_state.model_dump_json()
        size_bytes = len(json_str.encode('utf-8'))
        
        # Should be under 8KB (8192 bytes)
        assert size_bytes < 8192, f"AgentState size {size_bytes} bytes exceeds 8KB limit"
        print(f"AgentState size: {size_bytes} bytes (under 8KB limit)")


class TestAgentStateValidation:
    """Test AgentState validation and constraints."""
    
    def test_required_fields_validation(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            AgentState()  # Missing required fields
        
        errors = exc_info.value.errors()
        required_fields = {"user_id", "session_id", "raw_query"}
        error_fields = {error["loc"][0] for error in errors if error["type"] == "missing"}
        
        assert required_fields.issubset(error_fields), f"Missing validation for required fields: {required_fields - error_fields}"
    
    def test_state_version_constraint(self):
        """Test that state_version is correctly constrained."""
        state = AgentState(
            trace_id="version-test",
            user_id="user",
            session_id="session",
            raw_query="test query"
        )
        
        assert state.state_version == "v1"
        
        # Test that we can't set invalid version
        with pytest.raises(ValidationError):
            AgentState(
                trace_id="version-test",
                user_id="user", 
                session_id="session",
                raw_query="test query",
                state_version="invalid_version"
            )
    
    def test_citation_validation(self):
        """Test Citation model validation."""
        # Valid citation
        citation = Citation(
            doc_key="test_doc.json",
            page=5,
            snippet_range=(100, 200),
            confidence=0.85
        )
        
        assert citation.doc_key == "test_doc.json"
        assert citation.page == 5
        assert citation.snippet_range == (100, 200)
        assert citation.confidence == 0.85
        
        # Invalid confidence (outside 0-1 range)
        with pytest.raises(ValidationError):
            Citation(
                doc_key="test_doc.json",
                confidence=1.5  # Invalid: > 1.0
            )
        
        with pytest.raises(ValidationError):
            Citation(
                doc_key="test_doc.json", 
                confidence=-0.1  # Invalid: < 0.0
            )


class TestAgentStateEvolution:
    """Test AgentState schema evolution and backwards compatibility."""
    
    def test_backwards_compatibility_v1(self):
        """Test that v1 schema can handle missing optional fields."""
        # Simulate old data missing some fields
        old_data = {
            "state_version": "v1",
            "trace_id": "old-trace-123",
            "user_id": "old-user",
            "session_id": "old-session", 
            "raw_query": "old query",
            # Missing newer fields like synthesis_prompt_key
        }
        
        state = AgentState.model_validate(old_data)
        
        assert state.trace_id == "old-trace-123"
        assert state.synthesis_prompt_key is None  # Should default to None
        assert state.safety_flags == {}  # Should default to empty dict
    
    def test_state_progressive_updates(self):
        """Test that AgentState can be progressively updated through the pipeline."""
        # Start with minimal state
        state = AgentState(
            trace_id="progressive-test",
            user_id="user",
            session_id="session",
            raw_query="What is minimum wage?"
        )
        
        # Simulate intent router update
        state.intent = "rag_qa"
        state.jurisdiction = "ZW"
        
        # Simulate rewrite & expand update  
        state.rewritten_query = "Minimum wage requirements in Zimbabwe"
        state.hypothetical_docs = ["Document about wage laws", "Guide to employment"]
        
        # Simulate retrieval update
        state.candidate_chunk_ids = ["chunk1", "chunk2", "chunk3"]
        state.reranked_chunk_ids = ["chunk2", "chunk1"]
        
        # Simulate synthesis update
        state.final_answer = "The minimum wage in Zimbabwe is..."
        state.cited_sources = [
            Citation(doc_key="wage_act.json", confidence=0.9)
        ]
        
        # Verify all updates preserved
        assert state.intent == "rag_qa"
        assert state.jurisdiction == "ZW"
        assert len(state.hypothetical_docs) == 2
        assert len(state.candidate_chunk_ids) == 3
        assert len(state.reranked_chunk_ids) == 2
        assert state.final_answer.startswith("The minimum wage")
        assert len(state.cited_sources) == 1


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/api/test_agent_state.py -v
    pytest.main([__file__, "-v"])
