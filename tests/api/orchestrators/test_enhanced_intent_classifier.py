"""
Tests for ARCH-047 and ARCH-048: Enhanced Heuristic Intent Classifier

Tests the advanced heuristic classification with:
- User type detection (professional vs citizen)
- Intent pattern matching (constitutional, statutory, case law, procedural, rights)
- Complexity assessment (simple, moderate, complex, expert)
- Automatic calculation of retrieval parameters
- Confidence scoring
"""

import pytest
from api.orchestrators.query_orchestrator import QueryOrchestrator


@pytest.fixture
def orchestrator():
    """Create a QueryOrchestrator instance for testing."""
    return QueryOrchestrator()


class TestUserTypeDetection:
    """Test user type detection (professional vs citizen)."""
    
    def test_professional_indicators_act_chapter(self, orchestrator):
        """Professional indicators: Act [Chapter reference]."""
        result = orchestrator._classify_intent_heuristic(
            "What does the Labour Act [Chapter 28:01] say about minimum wage?"
        )
        assert result is not None
        assert result["user_type"] == "professional"
        assert result["confidence"] >= 0.8
    
    def test_professional_indicators_section_number(self, orchestrator):
        """Professional indicators: section with number."""
        result = orchestrator._classify_intent_heuristic(
            "Explain section 65(3) of the Companies Act"
        )
        assert result is not None
        assert result["user_type"] == "professional"
    
    def test_professional_indicators_case_citation(self, orchestrator):
        """Professional indicators: case v. citation."""
        result = orchestrator._classify_intent_heuristic(
            "What was held in Smith v. Jones SC 45/2020?"
        )
        assert result is not None
        assert result["user_type"] == "professional"
    
    def test_professional_indicators_legal_terms(self, orchestrator):
        """Professional indicators: legal terminology."""
        result = orchestrator._classify_intent_heuristic(
            "What is the ratio decidendi of this precedent?"
        )
        assert result is not None
        assert result["user_type"] == "professional"
    
    def test_citizen_default(self, orchestrator):
        """Citizen type for general queries."""
        result = orchestrator._classify_intent_heuristic(
            "Can I get a refund if my employer doesn't pay me?"
        )
        assert result is not None
        assert result["user_type"] == "citizen"


class TestIntentPatterns:
    """Test intent pattern matching."""
    
    def test_conversational_intent(self, orchestrator):
        """Conversational patterns should be detected."""
        conversational_queries = [
            "Hello",
            "Hi there",
            "Thanks for your help",
            "Good morning",
            "Bye"
        ]
        
        for query in conversational_queries:
            result = orchestrator._classify_intent_heuristic(query)
            assert result is not None
            assert result["intent"] == "conversational"
            assert result["complexity"] == "simple"
            assert result["confidence"] >= 0.9
            assert result["retrieval_top_k"] == 0  # No retrieval needed
    
    def test_summarization_intent(self, orchestrator):
        """Summarization patterns should be detected."""
        summarize_queries = [
            "Can you summarize that?",
            "Give me a summary",
            "Explain that in simple terms",
            "Break it down for me"
        ]
        
        for query in summarize_queries:
            result = orchestrator._classify_intent_heuristic(query)
            assert result is not None
            assert result["intent"] == "summarize"
            assert result["complexity"] == "simple"
            assert result["retrieval_top_k"] == 0
    
    def test_constitutional_interpretation(self, orchestrator):
        """Constitutional queries should be complex."""
        result = orchestrator._classify_intent_heuristic(
            "What are my fundamental rights under the constitution?"
        )
        assert result is not None
        assert result["intent"] == "rag_qa"
        assert result["reasoning_framework"] == "constitutional"
        assert result["complexity"] == "complex"
        assert result["confidence"] >= 0.85
        assert "constitutional_law" in result["legal_areas"]
        assert result["retrieval_top_k"] == 40  # Complex queries need more docs
    
    def test_statutory_analysis(self, orchestrator):
        """Statutory queries should use statutory framework."""
        result = orchestrator._classify_intent_heuristic(
            "What does section 5 of the Labour Act say?"
        )
        assert result is not None
        assert result["intent"] == "rag_qa"
        assert result["reasoning_framework"] == "statutory"
        assert result["complexity"] in ["moderate", "complex"]
        assert result["confidence"] >= 0.8
    
    def test_case_law_research(self, orchestrator):
        """Case law queries should be complex."""
        result = orchestrator._classify_intent_heuristic(
            "What is the precedent on employer liability?"
        )
        assert result is not None
        assert result["intent"] == "rag_qa"
        assert result["reasoning_framework"] == "precedent"
        assert result["complexity"] == "complex"
        assert "case_law" in result["legal_areas"]
    
    def test_procedural_inquiry(self, orchestrator):
        """Procedural queries should be simple."""
        result = orchestrator._classify_intent_heuristic(
            "How do I file a case at the Labour Court?"
        )
        assert result is not None
        assert result["intent"] == "rag_qa"
        assert result["complexity"] == "simple"
        assert "procedure" in result["legal_areas"]
        assert result["retrieval_top_k"] == 15  # Simple queries need fewer docs
    
    def test_rights_inquiry(self, orchestrator):
        """Rights inquiries should be citizen-focused and simple."""
        result = orchestrator._classify_intent_heuristic(
            "Can I sue my employer for unfair dismissal?"
        )
        assert result is not None
        assert result["intent"] == "rag_qa"
        assert result["complexity"] == "simple"
        assert result["user_type"] == "citizen"
        assert result["confidence"] >= 0.8
    
    def test_disambiguation(self, orchestrator):
        """Disambiguation queries should be detected."""
        result = orchestrator._classify_intent_heuristic(
            "What do you mean by that?"
        )
        assert result is not None
        assert result["intent"] == "disambiguate"
        assert result["complexity"] == "simple"


class TestComplexityAssessment:
    """Test complexity assessment logic."""
    
    def test_simple_complexity_short_query(self, orchestrator):
        """Short queries with few legal terms are simple."""
        result = orchestrator._classify_intent_heuristic(
            "What is minimum wage?"
        )
        assert result is not None
        assert result["complexity"] == "simple"
        assert result["retrieval_top_k"] == 15
        assert result["rerank_top_k"] == 5
    
    def test_moderate_complexity_medium_query(self, orchestrator):
        """Medium queries with some legal terms are moderate."""
        result = orchestrator._classify_intent_heuristic(
            "What are the legal requirements for registering a company in Zimbabwe?"
        )
        assert result is not None
        assert result["complexity"] == "moderate"
        assert result["retrieval_top_k"] == 25
        assert result["rerank_top_k"] == 8
    
    def test_complex_long_query(self, orchestrator):
        """Long queries with multiple concepts are complex."""
        result = orchestrator._classify_intent_heuristic(
            "What are the differences between retrenchment and dismissal "
            "under the Labour Act, and what are the legal obligations of employers "
            "in each case regarding notice period and compensation?"
        )
        assert result is not None
        assert result["complexity"] == "complex"
        assert result["retrieval_top_k"] == 40
        assert result["rerank_top_k"] == 12
    
    def test_complex_multiple_concepts(self, orchestrator):
        """Queries with 'and'/'or'/'versus' and legal terms are complex."""
        result = orchestrator._classify_intent_heuristic(
            "Compare the rights of employees versus contractors under labour law"
        )
        assert result is not None
        assert result["complexity"] == "complex"


class TestLegalAreaExtraction:
    """Test legal area extraction."""
    
    def test_labour_law_area(self, orchestrator):
        """Labour-related queries should be tagged."""
        result = orchestrator._classify_intent_heuristic(
            "What are the employment rights in the Labour Act?"
        )
        assert result is not None
        assert "labour_law" in result["legal_areas"]
    
    def test_company_law_area(self, orchestrator):
        """Company-related queries should be tagged."""
        result = orchestrator._classify_intent_heuristic(
            "What are the duties of company directors?"
        )
        assert result is not None
        assert "company_law" in result["legal_areas"]
    
    def test_criminal_law_area(self, orchestrator):
        """Criminal-related queries should be tagged."""
        result = orchestrator._classify_intent_heuristic(
            "What is the penalty for theft under criminal law?"
        )
        assert result is not None
        assert "criminal_law" in result["legal_areas"]
    
    def test_general_area_fallback(self, orchestrator):
        """Queries without specific area should be tagged as general."""
        result = orchestrator._classify_intent_heuristic(
            "What does the law say about property rights?"
        )
        assert result is not None
        assert "general" in result["legal_areas"]


class TestConfidenceScoring:
    """Test confidence scoring."""
    
    def test_high_confidence_conversational(self, orchestrator):
        """Conversational patterns have high confidence."""
        result = orchestrator._classify_intent_heuristic("Hello")
        assert result is not None
        assert result["confidence"] >= 0.9
    
    def test_high_confidence_constitutional(self, orchestrator):
        """Constitutional patterns have high confidence."""
        result = orchestrator._classify_intent_heuristic(
            "What are fundamental rights under the constitution?"
        )
        assert result is not None
        assert result["confidence"] >= 0.85
    
    def test_moderate_confidence_general(self, orchestrator):
        """General legal queries have moderate confidence."""
        result = orchestrator._classify_intent_heuristic(
            "What are the legal rules about contracts?"
        )
        assert result is not None
        assert result["confidence"] >= 0.7
    
    def test_uncertain_returns_none(self, orchestrator):
        """Non-legal queries should return None (trigger LLM)."""
        result = orchestrator._classify_intent_heuristic(
            "What is the weather today?"
        )
        assert result is None


class TestRetrievalParameters:
    """Test automatic calculation of retrieval parameters."""
    
    def test_simple_params(self, orchestrator):
        """Simple queries: 15 retrieval, 5 rerank."""
        result = orchestrator._classify_intent_heuristic(
            "How do I file a court case?"
        )
        assert result is not None
        assert result["retrieval_top_k"] == 15
        assert result["rerank_top_k"] == 5
    
    def test_moderate_params(self, orchestrator):
        """Moderate queries: 25 retrieval, 8 rerank."""
        result = orchestrator._classify_intent_heuristic(
            "What are the legal requirements for company registration?"
        )
        assert result is not None
        assert result["retrieval_top_k"] == 25
        assert result["rerank_top_k"] == 8
    
    def test_complex_params(self, orchestrator):
        """Complex queries: 40 retrieval, 12 rerank."""
        result = orchestrator._classify_intent_heuristic(
            "What are my constitutional rights regarding freedom of speech?"
        )
        assert result is not None
        assert result["retrieval_top_k"] == 40
        assert result["rerank_top_k"] == 12


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_query(self, orchestrator):
        """Empty query should return None."""
        result = orchestrator._classify_intent_heuristic("")
        assert result is None
    
    def test_whitespace_only(self, orchestrator):
        """Whitespace-only query should return None."""
        result = orchestrator._classify_intent_heuristic("   ")
        assert result is None
    
    def test_mixed_case_detection(self, orchestrator):
        """Case-insensitive pattern matching."""
        result = orchestrator._classify_intent_heuristic(
            "WHAT ARE MY CONSTITUTIONAL RIGHTS?"
        )
        assert result is not None
        assert result["reasoning_framework"] == "constitutional"
    
    def test_punctuation_handling(self, orchestrator):
        """Punctuation should not affect classification."""
        result1 = orchestrator._classify_intent_heuristic(
            "What are my rights?"
        )
        result2 = orchestrator._classify_intent_heuristic(
            "What are my rights"
        )
        assert result1 is not None
        assert result2 is not None
        assert result1["intent"] == result2["intent"]


@pytest.mark.asyncio
class TestIntegrationWithRouteIntentNode:
    """
    Test the integration of enhanced heuristics in _route_intent_node.
    ARCH-048: Update Intent Classifier to use enhanced heuristics with cache.
    """
    
    async def test_high_confidence_heuristic_used(self, orchestrator):
        """High confidence heuristic result should be used directly."""
        from api.schemas.agent_state import AgentState
        
        state = AgentState(
            raw_query="Hello, how are you?",
            user_id="test_user",
            session_id="test_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        assert result["intent"] == "conversational"
        assert result["complexity"] == "simple"
        assert result["intent_confidence"] >= 0.9
    
    async def test_constitutional_query_classification(self, orchestrator):
        """Constitutional query should be classified as complex."""
        from api.schemas.agent_state import AgentState
        
        state = AgentState(
            raw_query="What are my fundamental rights under the constitution?",
            user_id="test_user",
            session_id="test_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        assert result["intent"] == "rag_qa"
        assert result["complexity"] == "complex"
        assert result["reasoning_framework"] == "constitutional"
        assert result["retrieval_top_k"] == 40
        assert result["rerank_top_k"] == 12
    
    async def test_procedural_query_classification(self, orchestrator):
        """Procedural query should be classified as simple."""
        from api.schemas.agent_state import AgentState
        
        state = AgentState(
            raw_query="How do I file a case at court?",
            user_id="test_user",
            session_id="test_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        assert result["intent"] == "rag_qa"
        assert result["complexity"] == "simple"
        assert result["retrieval_top_k"] == 15
        assert result["rerank_top_k"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

