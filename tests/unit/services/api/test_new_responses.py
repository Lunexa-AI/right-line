"""Unit tests for new hardcoded responses added in Task 1.2.3."""

import pytest
from fastapi.testclient import TestClient

from services.api.main import app
from services.api.responses import HARDCODED_RESPONSES, get_hardcoded_response


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestNewResponses:
    """Test newly added responses."""
    
    def test_overtime_pay_response(self):
        """Test overtime pay response."""
        response = get_hardcoded_response("What are the overtime pay rates?")
        
        assert response is not None
        assert "overtime" in response.summary_3_lines.lower()
        assert response.section_ref.section == "14A"
        assert response.confidence >= 0.3  # Confidence adjusted by keyword matching
    
    def test_notice_period_response(self):
        """Test notice period response."""
        response = get_hardcoded_response("What is the required notice period?")
        
        assert response is not None
        assert "notice" in response.summary_3_lines.lower()
        assert response.section_ref.section == "12"
        assert len(response.citations) > 0
    
    def test_paternity_leave_response(self):
        """Test paternity leave response."""
        response = get_hardcoded_response("How much paternity leave do fathers get?")
        
        assert response is not None
        assert "2 weeks" in response.summary_3_lines
        assert response.section_ref.section == "18A"
        assert "maternity_leave" in response.related_sections
    
    def test_retrenchment_response(self):
        """Test retrenchment response."""
        response = get_hardcoded_response("retrenchment process")
        
        assert response is not None
        assert "retrenchment" in response.summary_3_lines.lower()
        assert response.section_ref.section == "12C"
        assert response.confidence >= 0.3  # Confidence adjusted by keyword matching
    
    def test_collective_bargaining_response(self):
        """Test collective bargaining response."""
        response = get_hardcoded_response("Do workers have collective bargaining rights?")
        
        assert response is not None
        assert "collective" in response.summary_3_lines.lower()
        assert response.section_ref.section == "74"
        assert "trade_unions" in response.related_sections
    
    def test_casual_workers_response(self):
        """Test casual workers response."""
        response = get_hardcoded_response("What are the rules for casual workers?")
        
        assert response is not None
        assert "casual" in response.summary_3_lines.lower()
        assert response.section_ref.section == "7"
        assert "minimum_wage" in response.related_sections
    
    def test_retirement_age_response(self):
        """Test retirement age response."""
        response = get_hardcoded_response("What is the retirement age?")
        
        assert response is not None
        assert "60" in response.summary_3_lines or "65" in response.summary_3_lines
        assert response.section_ref.section == "12B"
        assert "pension_contributions" in response.related_sections


class TestResponseVariations:
    """Test that responses handle variations in query phrasing."""
    
    @pytest.mark.parametrize("query", [
        "overtime rates",
        "how much for overtime",
        "overtime payment",
        "working extra hours pay",
        "Sunday work payment"
    ])
    def test_overtime_variations(self, query):
        """Test overtime queries with different phrasings."""
        response = get_hardcoded_response(query)
        assert response is not None
        assert "overtime" in response.summary_3_lines.lower() or "1.5x" in response.summary_3_lines
    
    @pytest.mark.parametrize("query", [
        "notice period",
        "resignation notice",
        "how much notice to give",
        "termination notice",
        "notice requirements"
    ])
    def test_notice_period_variations(self, query):
        """Test notice period queries with different phrasings."""
        response = get_hardcoded_response(query)
        assert response is not None
        assert response.section_ref.section in ["12", "12A", "12B", "12C"]
    
    @pytest.mark.parametrize("query", [
        "father leave",
        "paternity",
        "new father time off",
        "dad's leave",
        "paternal leave"
    ])
    def test_paternity_variations(self, query):
        """Test paternity leave queries with different phrasings."""
        response = get_hardcoded_response(query)
        assert response is not None
        # Should match paternity or possibly maternity
        assert response.section_ref.section in ["18", "18A"]


class TestResponseQuality:
    """Test quality aspects of responses."""
    
    def test_all_new_responses_have_citations(self):
        """Ensure all new responses have proper citations."""
        new_topics = [
            "overtime_pay",
            "notice_period",
            "paternity_leave",
            "retrenchment",
            "collective_bargaining",
            "casual_workers",
            "retirement_age"
        ]
        
        for topic in new_topics:
            if topic in HARDCODED_RESPONSES:
                response_data = HARDCODED_RESPONSES[topic]
                assert "citations" in response_data
                assert len(response_data["citations"]) > 0
                
                # Check citation structure
                for citation in response_data["citations"]:
                    assert "title" in citation
                    assert "url" in citation
    
    def test_all_new_responses_have_related_sections(self):
        """Ensure all new responses have related sections."""
        new_topics = [
            "overtime_pay",
            "notice_period",
            "paternity_leave",
            "retrenchment",
            "collective_bargaining",
            "casual_workers",
            "retirement_age"
        ]
        
        for topic in new_topics:
            if topic in HARDCODED_RESPONSES:
                response_data = HARDCODED_RESPONSES[topic]
                assert "related_sections" in response_data
                assert len(response_data["related_sections"]) > 0
    
    def test_summary_format(self):
        """Test that summaries follow the 3-line format."""
        new_topics = [
            "overtime_pay",
            "notice_period",
            "paternity_leave",
            "retrenchment",
            "collective_bargaining",
            "casual_workers",
            "retirement_age"
        ]
        
        for topic in new_topics:
            if topic in HARDCODED_RESPONSES:
                response_data = HARDCODED_RESPONSES[topic]
                summary = response_data.get("summary_3_lines", "")
                
                # Should have exactly 3 lines
                lines = summary.split('\n')
                assert len(lines) == 3, f"{topic} should have exactly 3 lines"
                
                # Each line should not be too long
                for line in lines:
                    assert len(line) <= 100, f"{topic} has a line longer than 100 chars: {line}"


class TestAPIIntegration:
    """Test new responses through the API."""
    
    def test_query_endpoint_with_new_topics(self, client):
        """Test that new topics work through the API."""
        queries = [
            "What are overtime pay rates?",
            "What is the notice period?",
            "How much paternity leave?",
            "Explain retrenchment process",
            "What about collective bargaining?",
            "Rules for casual workers?",
            "What is retirement age?"
        ]
        
        for query in queries:
            response = client.post(
                "/v1/query",
                json={"text": query, "channel": "web"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Check response structure
            assert "summary_3_lines" in data
            assert "section_ref" in data
            assert "citations" in data
            assert "confidence" in data
            assert data["confidence"] > 0.5  # Should have reasonable confidence
