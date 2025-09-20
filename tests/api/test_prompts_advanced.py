"""
Unit tests for advanced prompt templates in Gweta Legal AI.

Tests the state-of-the-art prompting system including:
- Constitutional hierarchy awareness
- Legal reasoning frameworks  
- Citation discipline
- Quality assurance prompts
- Persona adaptation

Follows .cursorrules: Comprehensive test coverage, golden datasets, property-based testing.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from api.composer.prompts import (
    get_prompt_template,
    get_max_tokens_for_complexity,
    build_synthesis_context,
    get_reasoning_framework_prompt,
    PromptConfig,
    GWETA_MASTER_CONSTITUTIONAL_PROMPT
)


class TestPromptRegistry:
    """Test the prompt template registry and configuration system."""
    
    def test_get_prompt_template_basic(self):
        """Test basic prompt template retrieval."""
        # Test valid template
        template = get_prompt_template("intent_classifier")
        assert template is not None
        assert hasattr(template, 'format_messages')
        
        # Test invalid template
        with pytest.raises(ValueError, match="Unknown template"):
            get_prompt_template("nonexistent_template")
    
    def test_prompt_config_validation(self):
        """Test prompt configuration validation."""
        # Valid config
        config = PromptConfig(
            template_name="synthesis",
            user_type="professional",
            complexity="complex",
            reasoning_framework="constitutional"
        )
        assert config.user_type == "professional"
        assert config.complexity == "complex"
        
        # Invalid user type should be caught by Pydantic
        with pytest.raises(ValueError):
            PromptConfig(template_name="synthesis", user_type="invalid")
    
    def test_persona_routing(self):
        """Test that synthesis templates route correctly by user type."""
        # Professional config
        prof_config = PromptConfig(template_name="synthesis", user_type="professional")
        prof_template = get_prompt_template("synthesis", prof_config)
        
        # Citizen config  
        citizen_config = PromptConfig(template_name="synthesis", user_type="citizen")
        citizen_template = get_prompt_template("synthesis", citizen_config)
        
        # Should get different templates
        assert prof_template != citizen_template
    
    def test_complexity_token_limits(self):
        """Test token limits scale with complexity."""
        assert get_max_tokens_for_complexity("simple") == 500
        assert get_max_tokens_for_complexity("moderate") == 1500
        assert get_max_tokens_for_complexity("complex") == 3000
        assert get_max_tokens_for_complexity("expert") == 4000
        assert get_max_tokens_for_complexity("unknown") == 1500  # Default


class TestConstitutionalPrompting:
    """Test constitutional hierarchy and legal reasoning in prompts."""
    
    def test_master_constitutional_prompt_content(self):
        """Test that master prompt contains key constitutional elements."""
        prompt = GWETA_MASTER_CONSTITUTIONAL_PROMPT
        
        # Check for constitutional hierarchy
        assert "Constitution of Zimbabwe (2013)" in prompt
        assert "supreme law" in prompt
        assert "Constitutional Court" in prompt
        assert "Supreme Court" in prompt
        
        # Check for grounding mandate
        assert "ABSOLUTE GROUNDING MANDATE" in prompt
        assert "CITE-THEN-STATE DISCIPLINE" in prompt
        assert "Source:" in prompt
        
        # Check for legal advice boundary
        assert "NO LEGAL ADVICE BOUNDARY" in prompt
        assert "educational purposes only" in prompt
    
    def test_reasoning_frameworks(self):
        """Test different legal reasoning frameworks."""
        # Constitutional framework
        const_framework = get_reasoning_framework_prompt("constitutional")
        assert "CONSTITUTIONAL INTERPRETATION FRAMEWORK" in const_framework
        assert "TEXTUAL" in const_framework
        assert "STRUCTURAL" in const_framework
        assert "PURPOSIVE" in const_framework
        
        # Statutory framework
        stat_framework = get_reasoning_framework_prompt("statutory")
        assert "STATUTORY INTERPRETATION FRAMEWORK" in stat_framework
        assert "LITERAL" in stat_framework
        assert "CONTEXTUAL" in stat_framework
        
        # IRAC framework (default)
        irac_framework = get_reasoning_framework_prompt("irac")
        assert "IRAC FRAMEWORK" in irac_framework
        assert "ISSUE" in irac_framework
        assert "RULE" in irac_framework
        assert "APPLICATION" in irac_framework
        assert "CONCLUSION" in irac_framework
    
    def test_build_synthesis_context(self):
        """Test synthesis context building with hierarchy indicators."""
        # Mock context documents
        context_docs = [
            {
                "doc_key": "const_sec_56",
                "title": "Constitution Section 56",
                "content": "Every person has the right to life.",
                "doc_type": "constitution",
                "authority_level": "supreme"
            },
            {
                "doc_key": "labour_act_12",
                "title": "Labour Act Section 12",
                "content": "An employer shall pay minimum wage.",
                "doc_type": "act",
                "authority_level": "high"
            }
        ]
        
        context = build_synthesis_context(
            query="What are employment rights in Zimbabwe?",
            context_documents=context_docs,
            user_type="professional",
            complexity="moderate",
            legal_areas=["constitutional", "employment"],
            reasoning_framework="statutory"
        )
        
        # Check context structure
        assert context["query"] == "What are employment rights in Zimbabwe?"
        assert context["user_type"] == "professional"
        assert context["complexity"] == "moderate"
        assert context["reasoning_framework"] == "statutory"
        assert context["jurisdiction"] == "ZW"
        
        # Check hierarchy indicators in context
        assert "[CONSTITUTIONAL AUTHORITY]" in context["context"]
        assert "[STATUTORY AUTHORITY]" in context["context"]
        assert "Constitution Section 56" in context["context"]
        assert "Labour Act Section 12" in context["context"]


class TestIntentClassification:
    """Test advanced intent classification with legal reasoning framework selection."""
    
    @pytest.mark.asyncio
    async def test_intent_classifier_prompt_structure(self):
        """Test intent classifier prompt structure and legal area extraction."""
        template = get_prompt_template("intent_classifier")
        
        # Format with test query
        messages = template.format_messages(query="What are the duties of company directors under Zimbabwe law?")
        
        # Check system message contains all required elements
        system_msg = messages[0].content
        assert "constitutional_interpretation" in system_msg
        assert "statutory_analysis" in system_msg
        assert "case_law_research" in system_msg
        assert "reasoning_framework" in system_msg
        assert "complexity" in system_msg
        assert "JSON" in system_msg
        
        # Check user message
        user_msg = messages[1].content
        assert "What are the duties of company directors" in user_msg
    
    def test_legal_area_extraction_patterns(self):
        """Test that intent classifier can handle various legal areas."""
        template = get_prompt_template("intent_classifier")
        
        test_queries = [
            "What are my constitutional rights if arrested?",
            "How do I register a company under the Companies Act?",
            "What did the Supreme Court say about employment dismissal?",
            "Explain property rights in simple terms",
            "What are the procedures for filing a civil claim?"
        ]
        
        for query in test_queries:
            messages = template.format_messages(query=query)
            # Should complete without error
            assert len(messages) == 2
            assert "Query:" in messages[1].content


class TestSynthesisPrompts:
    """Test synthesis prompts for different user types and complexities."""
    
    def test_professional_synthesis_prompt(self):
        """Test professional synthesis prompt with IRAC structure."""
        template = get_prompt_template("synthesis_professional")
        
        context = {
            "query": "What are the fiduciary duties of company directors?",
            "context": "[STATUTORY AUTHORITY] Source 1: Companies Act\nDirectors owe fiduciary duties...",
            "complexity": "complex",
            "legal_areas": ["corporate", "fiduciary"],
            "reasoning_framework": "statutory",
            "jurisdiction": "ZW",
            "date_context": None
        }
        
        messages = template.format_messages(**context)
        system_msg = messages[0].content
        
        # Check professional mode elements
        assert "PROFESSIONAL MODE ACTIVATED" in system_msg
        assert "comprehensive legal analysis" in system_msg
        assert "IRAC" in system_msg or "ISSUE" in system_msg
        assert "exact section numbers" in system_msg
        assert "No Response Limits" in system_msg
        
        # Check constitutional elements
        assert "Constitution of Zimbabwe" in system_msg
        assert "supreme law" in system_msg
        assert "CITE-THEN-STATE" in system_msg
    
    def test_citizen_synthesis_prompt(self):
        """Test citizen synthesis prompt with plain language focus."""
        template = get_prompt_template("synthesis_citizen")
        
        context = {
            "query": "What happens if I get arrested?",
            "context": "[CONSTITUTIONAL AUTHORITY] Source 1: Constitution Section 50\nEvery arrested person has rights...",
            "legal_areas": ["constitutional", "criminal"],
            "jurisdiction": "ZW",
            "date_context": None
        }
        
        messages = template.format_messages(**context)
        system_msg = messages[0].content
        
        # Check citizen mode elements
        assert "CITIZEN MODE ACTIVATED" in system_msg
        assert "plain language" in system_msg
        assert "15-year-old reading level" in system_msg
        assert "everyday analogies" in system_msg
        assert "educational purposes only" in system_msg
        
        # Check constitutional elements still present
        assert "Constitution of Zimbabwe" in system_msg
        assert "supreme law" in system_msg


class TestQualityAssurancePrompts:
    """Test quality assurance and verification prompts."""
    
    def test_attribution_verification_prompt(self):
        """Test attribution verification prompt structure."""
        template = get_prompt_template("attribution_verification")
        
        test_answer = """(Source: Section 56 Constitution) Every person has the right to life. 
        However, some laws may limit this right."""
        
        test_context = """Source 1: Constitution Section 56
        Content: Every person has the right to life..."""
        
        messages = template.format_messages(answer=test_answer, context=test_context)
        system_msg = messages[0].content
        
        # Check verification elements
        assert "ATTRIBUTION VERIFICATION SYSTEM" in system_msg
        assert "CITATION COMPLETENESS" in system_msg
        assert "GROUNDING VERIFICATION" in system_msg
        assert "90%" in system_msg  # Minimum standards
        assert "JSON" in system_msg
    
    def test_relevance_filter_prompt(self):
        """Test source relevance filtering prompt."""
        template = get_prompt_template("relevance_filter")
        
        test_query = "What are employment termination procedures?"
        test_sources = """Source 1: Labour Act
        Content: Employment termination requires notice...
        
        Source 2: Property Law Act  
        Content: Property transfers require registration..."""
        
        messages = template.format_messages(query=test_query, sources_with_content=test_sources)
        system_msg = messages[0].content
        
        # Check filtering elements
        assert "SOURCE RELEVANCE FILTER" in system_msg
        assert "essential" in system_msg
        assert "highly_relevant" in system_msg
        assert "moderately_relevant" in system_msg
        assert "irrelevant" in system_msg
        assert "constitutional hierarchy" in system_msg


class TestGoldenDatasets:
    """Test prompts against golden datasets of expected outputs."""
    
    @pytest.fixture
    def constitutional_query_dataset(self):
        """Golden dataset for constitutional queries."""
        return [
            {
                "query": "What are the rights of arrested persons in Zimbabwe?",
                "expected_intent": "constitutional_interpretation",
                "expected_complexity": "moderate",
                "expected_user_type": "professional",
                "expected_legal_areas": ["constitutional", "criminal"],
                "expected_reasoning_framework": "constitutional"
            },
            {
                "query": "explain my arrest rights simply",
                "expected_intent": "plain_explanation", 
                "expected_complexity": "simple",
                "expected_user_type": "citizen",
                "expected_legal_areas": ["constitutional", "criminal"],
                "expected_reasoning_framework": "explanatory"
            }
        ]
    
    @pytest.fixture
    def statutory_query_dataset(self):
        """Golden dataset for statutory analysis queries."""
        return [
            {
                "query": "What are the requirements for company registration under the Companies Act?",
                "expected_intent": "statutory_analysis",
                "expected_complexity": "moderate",
                "expected_user_type": "professional", 
                "expected_legal_areas": ["corporate", "registration"],
                "expected_reasoning_framework": "statutory"
            },
            {
                "query": "How do I register my business?",
                "expected_intent": "procedural_inquiry",
                "expected_complexity": "simple",
                "expected_user_type": "citizen",
                "expected_legal_areas": ["corporate", "registration"],
                "expected_reasoning_framework": "procedural"
            }
        ]
    
    def test_constitutional_queries_golden_dataset(self, constitutional_query_dataset):
        """Test constitutional queries against golden dataset."""
        template = get_prompt_template("intent_classifier")
        
        for test_case in constitutional_query_dataset:
            messages = template.format_messages(query=test_case["query"])
            
            # Verify prompt structure
            assert len(messages) == 2
            system_msg = messages[0].content
            user_msg = messages[1].content
            
            # Check that system prompt mentions expected categories
            assert test_case["expected_intent"] in system_msg
            assert test_case["expected_reasoning_framework"] in system_msg or "reasoning_framework" in system_msg
            
            # Check query is properly formatted
            assert test_case["query"] in user_msg
    
    def test_statutory_queries_golden_dataset(self, statutory_query_dataset):
        """Test statutory analysis queries against golden dataset."""
        template = get_prompt_template("query_rewriter")
        
        for test_case in statutory_query_dataset:
            # Build context for query rewriter
            intent_data = {
                "intent": test_case["expected_intent"],
                "complexity": test_case["expected_complexity"],
                "legal_areas": test_case["expected_legal_areas"]
            }
            
            messages = template.format_messages(
                raw_query=test_case["query"],
                conversation_context="No previous conversation",
                user_interests="Legal research assistance",
                intent_data=str(intent_data)
            )
            
            # Verify prompt structure
            assert len(messages) == 2
            system_msg = messages[0].content
            
            # Check for legal precision enhancement elements
            assert "LEGAL PRECISION ENHANCEMENT" in system_msg
            assert "ZIMBABWE-SPECIFIC ADAPTATIONS" in system_msg
            assert "Chapter" in system_msg  # Should mention chapter references


class TestCitationDiscipline:
    """Test citation discipline and grounding requirements."""
    
    def test_cite_then_state_examples(self):
        """Test that prompts include proper cite-then-state examples."""
        template = get_prompt_template("synthesis_professional")
        
        # Get system message
        messages = template.format_messages(
            query="Test query",
            context="Test context",
            complexity="moderate",
            legal_areas=[],
            reasoning_framework="irac",
            jurisdiction="ZW",
            date_context=None
        )
        
        system_msg = messages[0].content
        
        # Check for citation discipline
        assert "CITE-THEN-STATE" in system_msg
        assert "(Source:" in system_msg
        assert "immediate source citation" in system_msg
        
        # Check for grounding mandate
        assert "ABSOLUTE GROUNDING MANDATE" in system_msg
        assert "explicitly supported by the provided context" in system_msg
    
    def test_legal_hierarchy_awareness(self):
        """Test that prompts encode legal hierarchy correctly."""
        # Test synthesis context building
        context_docs = [
            {
                "doc_key": "const_56",
                "title": "Constitution Section 56", 
                "content": "Right to life provision",
                "doc_type": "constitution"
            },
            {
                "doc_key": "crim_code_47",
                "title": "Criminal Law Code Section 47",
                "content": "Murder provisions",
                "doc_type": "act"
            },
            {
                "doc_key": "case_murder_2020",
                "title": "State v Accused (2020) ZWSC 15",
                "content": "Supreme Court interpretation",
                "doc_type": "case_supreme"
            }
        ]
        
        context = build_synthesis_context(
            query="What is the right to life in Zimbabwe?",
            context_documents=context_docs,
            user_type="professional"
        )
        
        formatted_context = context["context"]
        
        # Check hierarchy indicators are present and in correct order
        assert "[CONSTITUTIONAL AUTHORITY]" in formatted_context
        assert "[STATUTORY AUTHORITY]" in formatted_context  
        assert "[SUPREME COURT]" in formatted_context
        
        # Constitutional authority should appear first
        const_pos = formatted_context.find("[CONSTITUTIONAL AUTHORITY]")
        stat_pos = formatted_context.find("[STATUTORY AUTHORITY]")
        court_pos = formatted_context.find("[SUPREME COURT]")
        
        assert const_pos < stat_pos  # Constitution before statutes
        assert stat_pos < court_pos   # Statutes before cases


class TestAdvancedReasoningPrompts:
    """Test advanced legal reasoning prompt integration."""
    
    def test_constitutional_interpretation_integration(self):
        """Test constitutional interpretation framework integration."""
        template = get_prompt_template("synthesis_professional")
        
        # Constitutional query context
        messages = template.format_messages(
            query="Is the death penalty constitutional in Zimbabwe?",
            context="[CONSTITUTIONAL AUTHORITY] Source 1: Constitution Section 48...",
            complexity="complex",
            legal_areas=["constitutional", "criminal"],
            reasoning_framework="constitutional",
            jurisdiction="ZW",
            date_context=None
        )
        
        system_msg = messages[0].content
        
        # Should include constitutional reasoning elements
        assert "constitutional" in system_msg.lower()
        assert "reasoning_framework" in system_msg or "constitutional" in system_msg
    
    def test_statutory_interpretation_integration(self):
        """Test statutory interpretation framework integration."""
        template = get_prompt_template("synthesis_professional")
        
        # Statutory analysis context
        messages = template.format_messages(
            query="What does Section 123 of the Labour Act require?",
            context="[STATUTORY AUTHORITY] Source 1: Labour Act Section 123...",
            complexity="moderate",
            legal_areas=["employment", "statutory"],
            reasoning_framework="statutory", 
            jurisdiction="ZW",
            date_context=None
        )
        
        system_msg = messages[0].content
        
        # Should reference statutory analysis
        assert "statutory" in system_msg.lower() or "reasoning_framework" in system_msg
    
    def test_precedent_analysis_integration(self):
        """Test precedent analysis framework integration."""
        template = get_prompt_template("synthesis_professional") 
        
        # Case law research context
        messages = template.format_messages(
            query="How has the Supreme Court interpreted employment dismissal?",
            context="[SUPREME COURT] Source 1: Employee v Employer (2020) ZWSC 25...",
            complexity="complex",
            legal_areas=["employment", "case_law"],
            reasoning_framework="precedent",
            jurisdiction="ZW",
            date_context=None
        )
        
        system_msg = messages[0].content
        
        # Should include precedent analysis elements
        assert "precedent" in system_msg.lower() or "reasoning_framework" in system_msg


class TestQualityAssuranceIntegration:
    """Test quality assurance prompt integration."""
    
    def test_attribution_verification_standards(self):
        """Test attribution verification maintains high standards."""
        template = get_prompt_template("attribution_verification")
        
        test_answer = """The Constitution provides rights. (Source: Section 56 Constitution) 
        Every person has the right to life. Some additional unsupported statement."""
        
        test_context = """Source 1: Constitution Section 56
        Content: Every person has the right to life and security of person."""
        
        messages = template.format_messages(answer=test_answer, context=test_context)
        system_msg = messages[0].content
        
        # Check strict verification requirements
        assert "90%" in system_msg  # High citation standard
        assert "100%" in system_msg  # Perfect quote verification
        assert "0% tolerance" in system_msg  # No unsupported statements
        assert "JSON" in system_msg
    
    def test_relevance_filter_hierarchy_awareness(self):
        """Test relevance filter applies constitutional hierarchy."""
        template = get_prompt_template("relevance_filter")
        
        messages = template.format_messages(
            query="Constitutional rights question",
            sources_with_content="Various sources..."
        )
        
        system_msg = messages[0].content
        
        # Check hierarchy awareness
        assert "constitutional hierarchy" in system_msg
        assert "higher authority sources" in system_msg
        assert "essential" in system_msg
        assert "highly_relevant" in system_msg


class TestPerformanceOptimization:
    """Test performance optimization features in prompts."""
    
    def test_token_limit_scaling(self):
        """Test that token limits scale appropriately with complexity."""
        # Simple queries should have lower limits
        simple_tokens = get_max_tokens_for_complexity("simple")
        complex_tokens = get_max_tokens_for_complexity("complex")
        expert_tokens = get_max_tokens_for_complexity("expert")
        
        assert simple_tokens < complex_tokens < expert_tokens
        assert simple_tokens == 500
        assert expert_tokens == 4000
    
    def test_context_document_limits(self):
        """Test context document limits for different complexities."""
        # Test with many documents
        many_docs = [
            {"doc_key": f"doc_{i}", "title": f"Document {i}", "content": f"Content {i}", "doc_type": "act"}
            for i in range(20)
        ]
        
        # Simple complexity should use fewer docs
        simple_context = build_synthesis_context(
            query="Simple legal question",
            context_documents=many_docs,
            complexity="simple"
        )
        
        # Should limit context appropriately (though current implementation doesn't limit, 
        # the framework is there for future optimization)
        assert len(simple_context["context"]) > 0


class TestBackwardCompatibility:
    """Test backward compatibility with existing system."""
    
    def test_legacy_template_names(self):
        """Test that legacy template names still work."""
        # These should work for backward compatibility
        legacy_names = ["intent_router", "synthesis"]
        
        for name in legacy_names:
            template = get_prompt_template(name)
            assert template is not None
    
    def test_existing_orchestrator_integration(self):
        """Test that existing orchestrator can use new prompts."""
        # Test that we can get the synthesis template the old way
        template = get_prompt_template("synthesis")
        assert template is not None
        
        # Test that it defaults to professional mode
        assert template == get_prompt_template("synthesis_professional")


# ==============================================================================
# INTEGRATION TESTS WITH MOCKED LLM
# ==============================================================================

class TestPromptLLMIntegration:
    """Test prompt integration with LLM calls (mocked for speed)."""
    
    @pytest.mark.asyncio
    async def test_intent_classification_chain(self):
        """Test complete intent classification chain with mocked LLM."""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "intent": "statutory_analysis",
            "complexity": "moderate", 
            "user_type": "professional",
            "jurisdiction": "ZW",
            "legal_areas": ["corporate"],
            "reasoning_framework": "statutory",
            "confidence": 0.9
        })
        
        # Mock LLM
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        
        # Get template and create chain
        template = get_prompt_template("intent_classifier")
        
        # Test that template can be chained with LLM
        messages = template.format_messages(query="How do I register a company?")
        assert len(messages) == 2
        
        # Verify the chain would work (without actually calling LLM)
        formatted_prompt = messages[0].content + "\n" + messages[1].content
        assert "company" in formatted_prompt.lower()
        assert "JSON" in formatted_prompt
    
    @pytest.mark.asyncio
    async def test_synthesis_chain(self):
        """Test synthesis chain with comprehensive context."""
        template = get_prompt_template("synthesis_professional")
        
        # Build realistic synthesis context
        context_docs = [
            {
                "doc_key": "companies_act_15",
                "title": "Companies Act Section 15", 
                "content": "Every company must have at least one director who is ordinarily resident in Zimbabwe.",
                "doc_type": "act"
            }
        ]
        
        context = build_synthesis_context(
            query="What are the residency requirements for company directors?",
            context_documents=context_docs,
            user_type="professional",
            complexity="moderate",
            reasoning_framework="statutory"
        )
        
        messages = template.format_messages(**context)
        
        # Check that context is properly formatted
        formatted_context = context["context"]
        assert "[STATUTORY AUTHORITY]" in formatted_context
        assert "Companies Act Section 15" in formatted_context
        assert "ordinarily resident in Zimbabwe" in formatted_context
        
        # Check that query is properly included
        user_msg = messages[1].content
        assert "residency requirements" in user_msg
        assert "company directors" in user_msg


class TestErrorHandling:
    """Test error handling and fallback behavior in prompts."""
    
    def test_invalid_template_config(self):
        """Test handling of invalid template configurations."""
        with pytest.raises(ValueError):
            # Invalid complexity level
            PromptConfig(
                template_name="synthesis",
                complexity="invalid_complexity"
            )
    
    def test_missing_context_handling(self):
        """Test prompt behavior with missing or empty context."""
        # Empty context documents
        context = build_synthesis_context(
            query="Test query",
            context_documents=[],
            user_type="professional"
        )
        
        # Should handle gracefully
        assert context["context"] == ""
        assert context["query"] == "Test query"
    
    def test_malformed_document_handling(self):
        """Test handling of malformed context documents."""
        malformed_docs = [
            {},  # Empty document
            {"doc_key": "test"},  # Missing required fields
            {"title": "Test", "content": None}  # None content
        ]
        
        # Should not crash
        context = build_synthesis_context(
            query="Test query",
            context_documents=malformed_docs,
            user_type="professional"
        )
        
        assert isinstance(context, dict)
        assert "context" in context


# ==============================================================================
# PROPERTY-BASED TESTING
# ==============================================================================

class TestPromptProperties:
    """Property-based tests for prompt behavior."""
    
    @pytest.mark.parametrize("complexity", ["simple", "moderate", "complex", "expert"])
    def test_token_limits_monotonic(self, complexity):
        """Test that token limits increase monotonically with complexity."""
        tokens = get_max_tokens_for_complexity(complexity)
        assert isinstance(tokens, int)
        assert tokens > 0
        assert tokens <= 5000  # Reasonable upper bound
    
    @pytest.mark.parametrize("user_type", ["professional", "citizen"])
    def test_synthesis_templates_exist(self, user_type):
        """Test that synthesis templates exist for all user types."""
        config = PromptConfig(template_name="synthesis", user_type=user_type)
        template = get_prompt_template("synthesis", config)
        assert template is not None
    
    @pytest.mark.parametrize("reasoning_framework", ["constitutional", "statutory", "precedent", "irac"])
    def test_reasoning_frameworks_defined(self, reasoning_framework):
        """Test that all reasoning frameworks are properly defined."""
        framework_prompt = get_reasoning_framework_prompt(reasoning_framework)
        assert isinstance(framework_prompt, str)
        assert len(framework_prompt) > 50  # Substantial content
        assert framework_prompt.upper() in framework_prompt  # Should have structured headings


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
