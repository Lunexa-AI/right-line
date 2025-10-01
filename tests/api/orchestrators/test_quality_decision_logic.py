"""
Tests for ARCH-049: Quality Decision Logic

Tests the _decide_refinement_strategy method that decides whether to:
- Pass (quality is good)
- Refine synthesis (coherence/logic issues)
- Retrieve more (insufficient sources)
- Fail (max iterations reached)
"""

import pytest
from api.orchestrators.query_orchestrator import QueryOrchestrator
from api.schemas.agent_state import AgentState


@pytest.fixture
def orchestrator():
    """Create a QueryOrchestrator instance for testing."""
    return QueryOrchestrator()


class TestQualityDecisionLogic:
    """Test quality decision logic for self-correction."""
    
    def test_pass_high_confidence_quality(self, orchestrator):
        """High confidence quality should pass."""
        state = AgentState(
            raw_query="What is minimum wage?",
            user_id="test_user",
            session_id="test_session",
            quality_passed=True,
            quality_confidence=0.9,
            quality_issues=[],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "pass"
    
    def test_fail_max_iterations(self, orchestrator):
        """Max iterations (2) should return fail."""
        state = AgentState(
            raw_query="Complex query",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.5,
            quality_issues=["Some issue"],
            refinement_iteration=2
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "fail"
    
    def test_refine_coherence_issues(self, orchestrator):
        """Coherence issues should trigger refinement."""
        state = AgentState(
            raw_query="Legal analysis query",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.65,
            quality_issues=[
                "Logical coherence issues detected in reasoning",
                "Structure could be improved"
            ],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "refine_synthesis"
    
    def test_retrieve_more_source_issues(self, orchestrator):
        """Insufficient sources should trigger retrieval."""
        state = AgentState(
            raw_query="Detailed legal question",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.7,
            quality_issues=[
                "Insufficient sources for comprehensive analysis",
                "Missing coverage of key legal areas"
            ],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "retrieve_more"
    
    def test_refine_expert_low_confidence(self, orchestrator):
        """Expert complexity with low confidence should refine."""
        state = AgentState(
            raw_query="Complex constitutional question",
            user_id="test_user",
            session_id="test_session",
            complexity="expert",
            quality_passed=False,
            quality_confidence=0.65,
            quality_issues=["Some quality concerns"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "refine_synthesis"
    
    def test_pass_low_quality_default(self, orchestrator):
        """Low quality without specific issues should pass (avoid over-iteration)."""
        state = AgentState(
            raw_query="Simple query",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.5,
            quality_issues=["Generic quality concern"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "pass"
    
    def test_refine_moderate_confidence_with_issues(self, orchestrator):
        """Moderate confidence with issues should refine."""
        state = AgentState(
            raw_query="Analysis needed",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.7,
            quality_issues=[
                "Minor reasoning gaps",
                "Could be more comprehensive"
            ],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "refine_synthesis"
    
    def test_pass_at_iteration_1(self, orchestrator):
        """At iteration 1, moderate quality should pass to avoid over-iteration."""
        state = AgentState(
            raw_query="Query",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.55,
            quality_issues=["Some concern"],
            refinement_iteration=1
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        # Should pass because we're at iteration 1 and issues aren't severe
        assert decision == "pass"


class TestIssueAnalysis:
    """Test analysis of specific quality issues."""
    
    def test_detect_coherence_keywords(self, orchestrator):
        """Should detect coherence-related keywords."""
        coherence_issues = [
            "Coherence issues in the analysis",
            "Logical gaps in reasoning",
            "Poor organization of arguments",
            "Reasoning structure needs improvement"
        ]
        
        for issue in coherence_issues:
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                quality_passed=False,
                quality_confidence=0.6,
                quality_issues=[issue],
                refinement_iteration=0
            )
            
            decision = orchestrator._decide_refinement_strategy(state)
            assert decision == "refine_synthesis", f"Failed for issue: {issue}"
    
    def test_detect_source_keywords(self, orchestrator):
        """Should detect source-related keywords."""
        source_issues = [
            "Insufficient sources provided",
            "Missing key citations",
            "Incomplete coverage of the topic",
            "Additional sources needed"
        ]
        
        for issue in source_issues:
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                quality_passed=False,
                quality_confidence=0.7,
                quality_issues=[issue],
                refinement_iteration=0
            )
            
            decision = orchestrator._decide_refinement_strategy(state)
            assert decision == "retrieve_more", f"Failed for issue: {issue}"
    
    def test_prioritize_source_over_coherence(self, orchestrator):
        """Source issues should be prioritized over coherence issues."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.65,
            quality_issues=[
                "Coherence could be better",
                "Insufficient sources for full analysis"  # This should take priority
            ],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "retrieve_more"


class TestComplexityHandling:
    """Test handling of different complexity levels."""
    
    def test_simple_complexity_lenient(self, orchestrator):
        """Simple queries with moderate confidence and issues still get refined."""
        state = AgentState(
            raw_query="Simple question",
            user_id="test_user",
            session_id="test_session",
            complexity="simple",
            quality_passed=False,
            quality_confidence=0.6,
            quality_issues=["Minor issue"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        # Even simple queries get refined if confidence is 0.6 with issues
        assert decision == "refine_synthesis"
    
    def test_expert_complexity_strict(self, orchestrator):
        """Expert queries should be stricter."""
        state = AgentState(
            raw_query="Expert-level question",
            user_id="test_user",
            session_id="test_session",
            complexity="expert",
            quality_passed=False,
            quality_confidence=0.65,
            quality_issues=["Quality concerns"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        # Expert queries require higher quality
        assert decision == "refine_synthesis"
    
    def test_moderate_complexity_balanced(self, orchestrator):
        """Moderate queries should have balanced thresholds."""
        state = AgentState(
            raw_query="Moderate question",
            user_id="test_user",
            session_id="test_session",
            complexity="moderate",
            quality_passed=False,
            quality_confidence=0.7,
            quality_issues=["Some issue"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "refine_synthesis"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_no_quality_data(self, orchestrator):
        """Missing quality data should pass to avoid blocking."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        # Should pass when quality data is missing
        assert decision == "pass"
    
    def test_empty_issues_list(self, orchestrator):
        """Empty issues with low confidence should pass."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.5,
            quality_issues=[],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "pass"
    
    def test_confidence_exactly_0_8(self, orchestrator):
        """Confidence exactly at threshold (0.8) should pass."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=True,
            quality_confidence=0.8,
            quality_issues=[],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        # 0.8 is not > 0.8, but with quality_passed=True, should handle gracefully
        # In this case, it falls through to default pass
        assert decision == "pass"
    
    def test_confidence_boundary_0_5(self, orchestrator):
        """Confidence at 0.5 boundary should be handled."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.5,
            quality_issues=["Coherence issues"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        # 0.5 is not in range (0.5, 0.8), so coherence check won't trigger
        assert decision == "pass"
    
    def test_confidence_boundary_0_6(self, orchestrator):
        """Confidence at 0.6 boundary with issues should refine."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.6,
            quality_issues=["Some issue"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        # 0.6 is in range [0.6, 0.8) with issues, should refine
        assert decision == "refine_synthesis"


class TestIterationLimits:
    """Test iteration count handling."""
    
    def test_iteration_0_allows_refinement(self, orchestrator):
        """Iteration 0 should allow refinement."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.6,
            quality_issues=["Coherence issues"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "refine_synthesis"
    
    def test_iteration_1_allows_refinement(self, orchestrator):
        """Iteration 1 should still allow refinement for serious issues."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.6,
            quality_issues=["Coherence issues"],
            refinement_iteration=1,
            complexity="expert"
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        # At iteration 1 with expert complexity and low confidence
        assert decision in ["refine_synthesis", "pass"]
    
    def test_iteration_2_blocks_refinement(self, orchestrator):
        """Iteration 2 should block any refinement."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.3,
            quality_issues=["Severe coherence issues"],
            refinement_iteration=2,
            complexity="expert"
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "fail"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

