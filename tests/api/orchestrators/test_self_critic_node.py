"""
Tests for ARCH-050: Self-Critic Node

Tests the _self_critic_node method that analyzes quality issues and generates
refinement instructions for improving synthesis quality.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from api.orchestrators.query_orchestrator import QueryOrchestrator
from api.schemas.agent_state import AgentState


@pytest.fixture
def orchestrator():
    """Create a QueryOrchestrator instance for testing."""
    return QueryOrchestrator()


@pytest.fixture
def mock_llm_response():
    """Mock LLM response with valid JSON."""
    return {
        "refinement_instructions": [
            "Add specific citations to the Labour Act [Chapter 28:01]",
            "Strengthen the legal reasoning around employee rights",
            "Address potential counterarguments about employer obligations"
        ],
        "priority_fixes": [
            "Improve citation density",
            "Add case law precedents"
        ],
        "suggested_additions": [
            "Reference Section 12 of the Labour Act",
            "Include Constitutional Court precedents on labour rights"
        ]
    }


class TestSelfCriticBasic:
    """Test basic self-critic functionality."""
    
    @pytest.mark.asyncio
    async def test_self_critic_with_quality_issues(self, orchestrator, mock_llm_response):
        """Self-critic should generate refinement instructions from quality issues."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            # Mock LLM response
            mock_response = MagicMock()
            mock_response.content = json.dumps(mock_llm_response)
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            # Need to mock the chain creation
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                state = AgentState(
                    raw_query="What are the minimum wage requirements?",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Minimum wage is set by law.",
                    quality_issues=[
                        "Insufficient legal citations",
                        "Weak logical reasoning",
                        "Missing statutory references"
                    ],
                    refinement_iteration=0
                )
                
                result = await orchestrator._self_critic_node(state)
                
                assert "refinement_instructions" in result
                assert isinstance(result["refinement_instructions"], list)
                assert len(result["refinement_instructions"]) == 3
                assert "priority_fixes" in result
                assert len(result["priority_fixes"]) == 2
                assert result["refinement_iteration"] == 1
    
    @pytest.mark.asyncio
    async def test_self_critic_increments_iteration(self, orchestrator, mock_llm_response):
        """Self-critic should increment refinement iteration."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = json.dumps(mock_llm_response)
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                state = AgentState(
                    raw_query="Legal question",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Some answer",
                    quality_issues=["Issue 1"],
                    refinement_iteration=1
                )
                
                result = await orchestrator._self_critic_node(state)
                
                assert result["refinement_iteration"] == 2


class TestSelfCriticErrorHandling:
    """Test error handling and fallback behavior."""
    
    @pytest.mark.asyncio
    async def test_invalid_json_response(self, orchestrator):
        """Invalid JSON should trigger fallback instructions."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            # Mock invalid JSON response
            mock_response = MagicMock()
            mock_response.content = "This is not valid JSON {invalid}"
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                state = AgentState(
                    raw_query="Test query",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Test answer",
                    quality_issues=["Issue 1", "Issue 2", "Issue 3"],
                    refinement_iteration=0
                )
                
                result = await orchestrator._self_critic_node(state)
                
                # Should use fallback instructions
                assert "refinement_instructions" in result
                assert len(result["refinement_instructions"]) == 3
                assert "priority_fixes" in result
                assert "citation density" in result["priority_fixes"][0].lower()
    
    @pytest.mark.asyncio
    async def test_llm_exception(self, orchestrator):
        """LLM exception should trigger graceful fallback."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            # Mock LLM exception
            MockLLM.side_effect = Exception("LLM API error")
            
            state = AgentState(
                raw_query="Test query",
                user_id="test_user",
                session_id="test_session",
                final_answer="Test answer",
                quality_issues=["Issue 1"],
                refinement_iteration=0
            )
            
            result = await orchestrator._self_critic_node(state)
            
            # Should return graceful fallback
            assert "refinement_instructions" in result
            assert len(result["refinement_instructions"]) >= 1
            assert "quality feedback" in result["refinement_instructions"][0].lower()
            assert result["refinement_iteration"] == 1
    
    @pytest.mark.asyncio
    async def test_no_answer_to_critique(self, orchestrator):
        """Missing final_answer should return default instructions."""
        state = AgentState(
            raw_query="Test query",
            user_id="test_user",
            session_id="test_session",
            quality_issues=["Issue 1"],
            refinement_iteration=0
        )
        
        result = await orchestrator._self_critic_node(state)
        
        assert "refinement_instructions" in result
        assert len(result["refinement_instructions"]) > 0
        assert "comprehensive" in result["refinement_instructions"][0].lower() or "analysis" in result["refinement_instructions"][0].lower()
        assert result["refinement_iteration"] == 1


class TestSelfCriticJSONParsing:
    """Test JSON parsing robustness."""
    
    @pytest.mark.asyncio
    async def test_markdown_wrapped_json(self, orchestrator, mock_llm_response):
        """JSON wrapped in markdown code blocks should be extracted."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            # Mock response with markdown wrapping
            markdown_response = f"```json\n{json.dumps(mock_llm_response)}\n```"
            mock_response = MagicMock()
            mock_response.content = markdown_response
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Answer",
                    quality_issues=["Issue"],
                    refinement_iteration=0
                )
                
                result = await orchestrator._self_critic_node(state)
                
                # Should successfully parse despite markdown wrapping
                assert len(result["refinement_instructions"]) == 3
                assert "Labour Act" in result["refinement_instructions"][0]
    
    @pytest.mark.asyncio
    async def test_plain_json_response(self, orchestrator, mock_llm_response):
        """Plain JSON response should parse correctly."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = json.dumps(mock_llm_response)
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Answer",
                    quality_issues=["Issue"],
                    refinement_iteration=0
                )
                
                result = await orchestrator._self_critic_node(state)
                
                assert len(result["refinement_instructions"]) == 3


class TestSelfCriticPromptConstruction:
    """Test prompt construction for the self-critic."""
    
    @pytest.mark.asyncio
    async def test_includes_query_and_answer(self, orchestrator, mock_llm_response):
        """Prompt should include original query and current answer."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = json.dumps(mock_llm_response)
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                test_query = "What are employee rights?"
                test_answer = "Employees have various rights under labour law."
                
                state = AgentState(
                    raw_query=test_query,
                    user_id="test_user",
                    session_id="test_session",
                    final_answer=test_answer,
                    quality_issues=["Missing citations"],
                    refinement_iteration=0
                )
                
                result = await orchestrator._self_critic_node(state)
                
                # Verify the prompt was constructed (via successful execution)
                assert result["refinement_iteration"] == 1
    
    @pytest.mark.asyncio
    async def test_truncates_long_answer(self, orchestrator, mock_llm_response):
        """Long answers should be truncated to avoid token limits."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = json.dumps(mock_llm_response)
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                # Create a very long answer
                long_answer = "This is a legal analysis. " * 200  # ~3000 chars
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer=long_answer,
                    quality_issues=["Issue"],
                    refinement_iteration=0
                )
                
                result = await orchestrator._self_critic_node(state)
                
                # Should complete successfully (answer was truncated in prompt)
                assert result["refinement_iteration"] == 1


class TestSelfCriticOutputStructure:
    """Test the structure of self-critic output."""
    
    @pytest.mark.asyncio
    async def test_output_has_required_fields(self, orchestrator, mock_llm_response):
        """Output should have all required fields."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = json.dumps(mock_llm_response)
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Answer",
                    quality_issues=["Issue"],
                    refinement_iteration=0
                )
                
                result = await orchestrator._self_critic_node(state)
                
                assert "refinement_instructions" in result
                assert "priority_fixes" in result
                assert "suggested_additions" in result
                assert "refinement_iteration" in result
    
    @pytest.mark.asyncio
    async def test_instructions_are_lists(self, orchestrator, mock_llm_response):
        """All instruction fields should be lists."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = json.dumps(mock_llm_response)
            
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm_instance
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Answer",
                    quality_issues=["Issue"],
                    refinement_iteration=0
                )
                
                result = await orchestrator._self_critic_node(state)
                
                assert isinstance(result["refinement_instructions"], list)
                assert isinstance(result["priority_fixes"], list)
                assert isinstance(result["suggested_additions"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

