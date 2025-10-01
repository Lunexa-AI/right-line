"""
Tests for ARCH-051: Refined Synthesis Node

Tests the _refined_synthesis_node method that regenerates synthesis using
refinement instructions from the self-critic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from api.orchestrators.query_orchestrator import QueryOrchestrator
from api.schemas.agent_state import AgentState


@pytest.fixture
def orchestrator():
    """Create a QueryOrchestrator instance for testing."""
    return QueryOrchestrator()


@pytest.fixture
def sample_context():
    """Sample bundled context documents."""
    return [
        {
            "parent_doc_id": "doc_1",
            "title": "Labour Act [Chapter 28:01]",
            "content": "Section 12 covers minimum wage provisions..." * 50,
            "source_type": "statute",
            "confidence": 0.9
        },
        {
            "parent_doc_id": "doc_2",
            "title": "Employment Regulations",
            "content": "Regulations regarding employment contracts..." * 50,
            "source_type": "regulation",
            "confidence": 0.75
        }
    ]


class TestRefinedSynthesisBasic:
    """Test basic refined synthesis functionality."""
    
    @pytest.mark.asyncio
    async def test_refined_synthesis_with_instructions(self, orchestrator, sample_context):
        """Should generate improved synthesis using refinement instructions."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            # Mock LLM response
            mock_response = MagicMock()
            mock_response.content = "This is an improved legal analysis with proper citations to Section 12 of the Labour Act [Chapter 28:01] addressing all refinement points."
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('api.composer.prompts.get_prompt_template') as mock_get_template, \
                 patch('api.composer.prompts.build_synthesis_context') as mock_build_context:
                
                # Mock template
                mock_template = MagicMock()
                mock_template.format_messages = MagicMock(return_value=[])
                mock_get_template.return_value = mock_template
                
                # Mock context builder
                mock_build_context.return_value = {
                    "query": "Test query",
                    "context_documents": []
                }
                
                state = AgentState(
                    raw_query="What is the minimum wage?",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Minimum wage is defined by law.",
                    bundled_context=sample_context,
                    refinement_instructions=[
                        "Add specific citations to Labour Act",
                        "Strengthen legal reasoning",
                        "Address counterarguments"
                    ],
                    priority_fixes=["Improve citation density"],
                    suggested_additions=["Reference Section 12"],
                    refinement_iteration=1
                )
                
                result = await orchestrator._refined_synthesis_node(state)
                
                assert "final_answer" in result
                assert len(result["final_answer"]) > 0
                assert "synthesis" in result
                assert result["synthesis"]["refined"] is True
                assert result["synthesis"]["iteration"] == 1
    
    @pytest.mark.asyncio
    async def test_no_instructions_returns_empty(self, orchestrator, sample_context):
        """Should return empty dict when no refinement instructions."""
        state = AgentState(
            raw_query="Test query",
            user_id="test_user",
            session_id="test_session",
            final_answer="Some answer",
            bundled_context=sample_context,
            refinement_instructions=[],  # No instructions
            refinement_iteration=1
        )
        
        result = await orchestrator._refined_synthesis_node(state)
        
        # Should return empty dict to keep original answer
        assert result == {}


class TestRefinedSynthesisPromptConstruction:
    """Test prompt construction for refined synthesis."""
    
    @pytest.mark.asyncio
    async def test_includes_all_refinement_sections(self, orchestrator, sample_context):
        """Prompt should include priority fixes, instructions, and additions."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = "Refined analysis"
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            captured_messages = None
            
            with patch('api.composer.prompts.get_prompt_template') as mock_get_template, \
                 patch('api.composer.prompts.build_synthesis_context') as mock_build_context:
                
                def capture_messages(**kwargs):
                    nonlocal captured_messages
                    captured_messages = kwargs
                    return [MagicMock()]
                
                mock_template = MagicMock()
                mock_template.format_messages = MagicMock(side_effect=capture_messages)
                mock_get_template.return_value = mock_template
                
                mock_build_context.return_value = {
                    "query": "original query",
                    "context_documents": []
                }
                
                state = AgentState(
                    raw_query="What is minimum wage?",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Basic answer",
                    bundled_context=sample_context,
                    refinement_instructions=["Add citations", "Improve logic"],
                    priority_fixes=["Critical fix 1"],
                    suggested_additions=["Add Section 12 reference"],
                    refinement_iteration=1
                )
                
                result = await orchestrator._refined_synthesis_node(state)
                
                # Check that refinement guidance was added to the synthesis context
                assert captured_messages is not None
                query = captured_messages.get("query", "")
                assert "REFINEMENT INSTRUCTIONS" in query
                assert "Priority Fixes" in query
                assert "Specific Instructions" in query
                assert "Suggested Additions" in query
                assert "PREVIOUS ANALYSIS" in query
    
    @pytest.mark.asyncio
    async def test_truncates_long_previous_answer(self, orchestrator, sample_context):
        """Should truncate previous answer to 500 chars."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = "Refined analysis"
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            captured_messages = None
            
            def capture_messages(**kwargs):
                nonlocal captured_messages
                captured_messages = kwargs
                return [MagicMock()]
            
            with patch('api.composer.prompts.get_prompt_template') as mock_get_template, \
                 patch('api.composer.prompts.build_synthesis_context') as mock_build:
                
                mock_template = MagicMock()
                mock_template.format_messages = MagicMock(side_effect=capture_messages)
                mock_get_template.return_value = mock_template
                
                mock_build.return_value = {"query": "test", "context_documents": []}
                
                long_answer = "This is a very long legal analysis. " * 100  # Very long
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer=long_answer,
                    bundled_context=sample_context,
                    refinement_instructions=["Improve"],
                    refinement_iteration=1
                )
                
                result = await orchestrator._refined_synthesis_node(state)
                
                # Previous analysis in query should be truncated
                query = captured_messages.get("query", "")
                assert "..." in query


class TestRefinedSynthesisComplexity:
    """Test complexity-based token limits."""
    
    @pytest.mark.asyncio
    async def test_simple_complexity_token_limit(self, orchestrator, sample_context):
        """Simple complexity should use 1000 tokens."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = "Refined"
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('api.composer.prompts.get_prompt_template') as mock_get_template, \
                 patch('api.composer.prompts.build_synthesis_context') as mock_build:
                
                mock_template = MagicMock()
                mock_template.format_messages = MagicMock(return_value=[])
                mock_get_template.return_value = mock_template
                mock_build.return_value = {"query": "test", "context_documents": []}
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    complexity="simple",
                    final_answer="Answer",
                    bundled_context=sample_context,
                    refinement_instructions=["Improve"],
                    refinement_iteration=1
                )
                
                await orchestrator._refined_synthesis_node(state)
                
                # Check that LLM was called with max_tokens=1000
                MockLLM.assert_called_once()
                call_kwargs = MockLLM.call_args[1]
                assert call_kwargs["max_tokens"] == 1000
    
    @pytest.mark.asyncio
    async def test_expert_complexity_token_limit(self, orchestrator, sample_context):
        """Expert complexity should use 2500 tokens."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = "Refined"
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('api.composer.prompts.get_prompt_template') as mock_get_template, \
                 patch('api.composer.prompts.build_synthesis_context') as mock_build:
                
                mock_template = MagicMock()
                mock_template.format_messages = MagicMock(return_value=[])
                mock_get_template.return_value = mock_template
                mock_build.return_value = {"query": "test", "context_documents": []}
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    complexity="expert",
                    final_answer="Answer",
                    bundled_context=sample_context,
                    refinement_instructions=["Improve"],
                    refinement_iteration=1
                )
                
                await orchestrator._refined_synthesis_node(state)
                
                # Check that LLM was called with max_tokens=2500
                MockLLM.assert_called_once()
                call_kwargs = MockLLM.call_args[1]
                assert call_kwargs["max_tokens"] == 2500


class TestRefinedSynthesisErrorHandling:
    """Test error handling and fallback behavior."""
    
    @pytest.mark.asyncio
    async def test_llm_exception_returns_empty(self, orchestrator, sample_context):
        """LLM exception should return empty dict to keep original."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            # Mock LLM exception
            MockLLM.side_effect = Exception("LLM API error")
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                final_answer="Original answer",
                bundled_context=sample_context,
                refinement_instructions=["Improve"],
                refinement_iteration=1
            )
            
            result = await orchestrator._refined_synthesis_node(state)
            
            # Should return empty dict to keep original answer
            assert result == {}
    
    @pytest.mark.asyncio
    async def test_missing_context_handled(self, orchestrator):
        """Missing bundled_context should be handled gracefully."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = "Refined with empty context"
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('api.composer.prompts.get_prompt_template') as mock_get_template, \
                 patch('api.composer.prompts.build_synthesis_context') as mock_build:
                
                mock_template = MagicMock()
                mock_template.format_messages = MagicMock(return_value=[])
                mock_get_template.return_value = mock_template
                mock_build.return_value = {"query": "test", "context_documents": []}
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Answer",
                    bundled_context=[],  # Empty context
                    refinement_instructions=["Improve"],
                    refinement_iteration=1
                )
                
                result = await orchestrator._refined_synthesis_node(state)
                
                # Should still complete with empty context
                assert "final_answer" in result


class TestRefinedSynthesisMetadata:
    """Test synthesis metadata tracking."""
    
    @pytest.mark.asyncio
    async def test_metadata_includes_lengths(self, orchestrator, sample_context):
        """Metadata should include original and refined lengths."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            refined_text = "This is a much longer and more detailed refined analysis." * 10
            mock_response = MagicMock()
            mock_response.content = refined_text
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('api.composer.prompts.get_prompt_template') as mock_get_template, \
                 patch('api.composer.prompts.build_synthesis_context') as mock_build:
                
                mock_template = MagicMock()
                mock_template.format_messages = MagicMock(return_value=[])
                mock_get_template.return_value = mock_template
                mock_build.return_value = {"query": "test", "context_documents": []}
                
                original_text = "Short original answer."
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer=original_text,
                    bundled_context=sample_context,
                    refinement_instructions=["Expand analysis"],
                    refinement_iteration=1
                )
                
                result = await orchestrator._refined_synthesis_node(state)
                
                assert result["synthesis"]["refined"] is True
                assert result["synthesis"]["original_length"] == len(original_text)
                assert result["synthesis"]["refined_length"] == len(refined_text)
                assert result["synthesis"]["iteration"] == 1


class TestRefinedSynthesisContextDocuments:
    """Test context document preparation."""
    
    @pytest.mark.asyncio
    async def test_limits_context_to_12_docs(self, orchestrator):
        """Should limit context to top 12 documents."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = "Refined"
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            captured_docs = None
            
            def capture_docs(**kwargs):
                nonlocal captured_docs
                captured_docs = kwargs.get("context_documents", [])
                return {"query": "test", "context_documents": captured_docs}
            
            with patch('api.composer.prompts.get_prompt_template') as mock_get_template, \
                 patch('api.composer.prompts.build_synthesis_context', side_effect=capture_docs):
                
                mock_template = MagicMock()
                mock_template.format_messages = MagicMock(return_value=[])
                mock_get_template.return_value = mock_template
                
                # Create 20 context documents
                large_context = [
                    {"parent_doc_id": f"doc_{i}", "title": f"Doc {i}", "content": f"Content {i}" * 100}
                    for i in range(20)
                ]
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Answer",
                    bundled_context=large_context,
                    refinement_instructions=["Improve"],
                    refinement_iteration=1
                )
                
                result = await orchestrator._refined_synthesis_node(state)
                
                # Should only use top 12 documents
                assert len(captured_docs) == 12


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

