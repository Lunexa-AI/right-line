"""Unit tests for RightLine API hardcoded responses."""

from __future__ import annotations

import pytest

from services.api.responses import (
    calculate_keyword_match_score,
    get_available_topics,
    get_hardcoded_response,
    get_response_by_topic,
    normalize_query,
)


class TestQueryNormalization:
    """Test query text normalization."""
    
    def test_normalize_basic_text(self):
        """Test basic text normalization."""
        result = normalize_query("What is the minimum wage?")
        assert result == "minimum wage"
    
    def test_normalize_removes_extra_whitespace(self):
        """Test that extra whitespace is removed."""
        result = normalize_query("  What   is    the   minimum   wage?  ")
        assert result == "minimum wage"
    
    def test_normalize_converts_to_lowercase(self):
        """Test that text is converted to lowercase."""
        result = normalize_query("WHAT IS THE MINIMUM WAGE?")
        assert result == "minimum wage"
    
    def test_normalize_removes_stop_words(self):
        """Test that common stop words are removed."""
        result = normalize_query("What is the minimum wage for workers?")
        assert result == "minimum wage workers"
    
    def test_normalize_preserves_legal_terms(self):
        """Test that important legal terms are preserved."""
        result = normalize_query("What are the working hours and overtime rules?")
        assert result == "working hours overtime rules"
    
    def test_normalize_empty_string(self):
        """Test normalization of empty string."""
        result = normalize_query("")
        assert result == ""
    
    def test_normalize_only_stop_words(self):
        """Test normalization when query contains only stop words."""
        result = normalize_query("what is the and or")
        assert result == ""


class TestKeywordMatching:
    """Test keyword matching functionality."""
    
    def test_exact_phrase_match(self):
        """Test exact phrase matching gets high score."""
        keywords = ["minimum wage", "salary"]
        query = "minimum wage"
        score = calculate_keyword_match_score(query, keywords)
        assert score >= 0.5  # Should get high score for exact match
    
    def test_partial_word_match(self):
        """Test partial word matching gets proportional score."""
        keywords = ["working hours"]
        query = "working"
        score = calculate_keyword_match_score(query, keywords)
        assert 0.0 < score < 1.0  # Should get partial score
    
    def test_no_match(self):
        """Test no matching keywords returns zero score."""
        keywords = ["minimum wage"]
        query = "banana price"
        score = calculate_keyword_match_score(query, keywords)
        assert score == 0.0
    
    def test_multiple_keyword_match(self):
        """Test matching multiple keywords increases score."""
        keywords = ["minimum wage", "salary", "pay"]
        query = "minimum wage pay"
        score = calculate_keyword_match_score(query, keywords)
        assert score > 0.5  # Should get good score for multiple matches
    
    def test_empty_keywords(self):
        """Test empty keywords list returns zero score."""
        keywords = []
        query = "minimum wage"
        score = calculate_keyword_match_score(query, keywords)
        assert score == 0.0


class TestHardcodedResponses:
    """Test hardcoded response generation."""
    
    def test_minimum_wage_query(self):
        """Test minimum wage query returns correct response."""
        response = get_hardcoded_response("What is the minimum wage in Zimbabwe?")
        
        assert response.section_ref.act == "Labour Act"
        assert response.section_ref.section == "12A"
        assert response.confidence > 0.5
        assert len(response.citations) > 0
        assert "minimum wage" in response.summary_3_lines.lower()
    
    def test_working_hours_query(self):
        """Test working hours query returns correct response."""
        response = get_hardcoded_response("How many hours can I work per day?")
        
        assert response.section_ref.act == "Labour Act"
        assert response.section_ref.section == "14"
        assert response.confidence > 0.5
        assert "hours" in response.summary_3_lines.lower()
    
    def test_leave_entitlement_query(self):
        """Test leave entitlement query returns correct response."""
        response = get_hardcoded_response("How much annual leave am I entitled to?")
        
        assert response.section_ref.act == "Labour Act"
        assert response.section_ref.section == "18"
        assert response.confidence > 0.5
        assert "leave" in response.summary_3_lines.lower()
    
    def test_termination_query(self):
        """Test termination query returns correct response."""
        response = get_hardcoded_response("Can my employer fire me without notice?")
        
        assert response.section_ref.act == "Labour Act"
        assert response.section_ref.section == "12"
        assert response.confidence > 0.5
        assert any(word in response.summary_3_lines.lower() 
                  for word in ["termination", "dismissal", "notice"])
    
    def test_contract_query(self):
        """Test employment contract query returns correct response."""
        response = get_hardcoded_response("Do I need a written employment contract?")
        
        assert response.section_ref.act == "Labour Act"
        assert response.section_ref.section == "5"
        assert response.confidence > 0.5
        assert "contract" in response.summary_3_lines.lower()
    
    def test_safety_query(self):
        """Test workplace safety query returns correct response."""
        response = get_hardcoded_response("What are my workplace safety rights?")
        
        assert response.section_ref.act == "Occupational Safety and Health Act"
        assert response.section_ref.section == "6"
        assert response.confidence > 0.5
        assert "safety" in response.summary_3_lines.lower()
    
    def test_discrimination_query(self):
        """Test discrimination query returns correct response."""
        response = get_hardcoded_response("Can my employer discriminate against me?")
        
        assert response.section_ref.act == "Labour Act"
        assert response.section_ref.section == "4"
        assert response.confidence > 0.5
        assert "discrimination" in response.summary_3_lines.lower()
    
    def test_union_query(self):
        """Test trade union query returns correct response."""
        response = get_hardcoded_response("Can I join a trade union?")
        
        assert response.section_ref.act == "Labour Act"
        assert response.section_ref.section == "25"
        assert response.confidence > 0.5
        assert "union" in response.summary_3_lines.lower()
    
    def test_unknown_query_returns_default(self):
        """Test unknown query returns default response."""
        response = get_hardcoded_response("What is the price of bananas?")
        
        assert response.section_ref.act == "General Information"
        assert response.section_ref.section == "FAQ"
        assert response.confidence < 0.5
        assert "couldn't find" in response.summary_3_lines.lower()
    
    def test_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        with pytest.raises(ValueError, match="Query text cannot be empty"):
            get_hardcoded_response("")
    
    def test_whitespace_only_query_raises_error(self):
        """Test whitespace-only query raises ValueError."""
        with pytest.raises(ValueError, match="Query text cannot be empty"):
            get_hardcoded_response("   ")
    
    def test_response_structure(self):
        """Test that response has correct structure."""
        response = get_hardcoded_response("minimum wage")
        
        # Check all required fields are present
        assert hasattr(response, 'summary_3_lines')
        assert hasattr(response, 'section_ref')
        assert hasattr(response, 'citations')
        assert hasattr(response, 'confidence')
        assert hasattr(response, 'related_sections')
        
        # Check types
        assert isinstance(response.summary_3_lines, str)
        assert isinstance(response.confidence, float)
        assert isinstance(response.citations, list)
        assert isinstance(response.related_sections, list)
        
        # Check confidence is in valid range
        assert 0.0 <= response.confidence <= 1.0
    
    def test_summary_line_count(self):
        """Test that summary has appropriate line count."""
        response = get_hardcoded_response("minimum wage")
        
        lines = response.summary_3_lines.split('\n')
        assert len(lines) <= 3  # Should not exceed 3 lines
        
        # Each line should not be too long
        for line in lines:
            assert len(line) <= 120  # Max line length from model validation
    
    def test_language_hint_parameter(self):
        """Test language hint parameter (currently not used but should not error)."""
        response = get_hardcoded_response("minimum wage", lang_hint="en")
        
        assert response.section_ref.act == "Labour Act"
        assert response.confidence > 0.5


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_get_available_topics(self):
        """Test getting list of available topics."""
        topics = get_available_topics()
        
        assert isinstance(topics, list)
        assert len(topics) > 0
        assert "minimum_wage" in topics
        assert "working_hours" in topics
        assert "leave_entitlement" in topics
    
    def test_get_response_by_topic_valid(self):
        """Test getting response by valid topic."""
        response_data = get_response_by_topic("minimum_wage")
        
        assert response_data is not None
        assert "keywords" in response_data
        assert "summary" in response_data
        assert "section_ref" in response_data
        assert "citations" in response_data
        assert "confidence" in response_data
    
    def test_get_response_by_topic_invalid(self):
        """Test getting response by invalid topic returns None."""
        response_data = get_response_by_topic("nonexistent_topic")
        
        assert response_data is None
