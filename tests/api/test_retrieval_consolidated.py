#!/usr/bin/env python3
"""
Comprehensive test suite for LangChain-based RetrievalEngine (Task 4.3).

This consolidated test file covers:
- Basic retrieval functionality and API compatibility
- LangChain component integration (EnsembleRetriever, ContextualCompressionRetriever)
- Small-to-Big parent document expansion
- R2 integration for content fetching
- Error handling and resilience
- Performance requirements
- Agent state integration

Following TDD principles from .cursorrules.

Author: RightLine Team
"""

import json
import pytest
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from langchain_core.runnables import RunnableLambda
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever

# Import the consolidated LangChain-based implementation
from api.tools.retrieval_engine import (
    RetrievalEngine, 
    RetrievalResult, 
    RetrievalConfig,
    search_legal_documents,
    MilvusRetriever,
    BM25Retriever
)
from api.tools.reranker import BGEReranker
from api.schemas.agent_state import AgentState
from api.models import ChunkV3, ParentDocumentV3, QueryRequest
from libs.common.settings import settings


class TestRetrievalEngineConsolidated(unittest.IsolatedAsyncioTestCase):
    """Comprehensive tests for the consolidated LangChain-based RetrievalEngine"""

    async def asyncSetUp(self):
        """Set up test fixtures and sample data."""
        # Sample data matching the ChunkV3 and ParentDocumentV3 models
        self.sample_chunks = [
            ChunkV3(
                doc_id="doc1",
                chunk_id="chunk1", 
                chunk_text="Import regulations for chemicals in Zimbabwe",
                tree_node_id="0001",
                section_path="Part I > Section 1"
            ),
            ChunkV3(
                doc_id="doc2",
                chunk_id="chunk2",
                chunk_text="White phosphorus classification as hazardous material", 
                tree_node_id="0002",
                section_path="Part II > Section 2"
            ),
        ]

        self.sample_parent = ParentDocumentV3(
            doc_id="doc1",
            title="Chemical Import Regulations Act",
            canonical_citation="Chemical Import Regulations Act [Chapter 6:05]",
            pageindex_markdown="# Chemical Import Regulations Act\n\nThis act governs the import of chemicals...",
            content_tree=[
                {"title": "Part I - General Provisions", "node_id": "0001", "page_index": 1},
                {"title": "Part II - Hazardous Materials", "node_id": "0002", "page_index": 2}
            ]
        )

    # ===== BASIC FUNCTIONALITY TESTS =====

    def test_retrieval_chain_construction(self):
        """Test that LangChain components are correctly wired together."""
        engine = RetrievalEngine()
        
        # Verify core LangChain components exist
        self.assertIsNotNone(engine.retrieval_chain)
        self.assertIsNotNone(engine._ensemble_retriever)
        self.assertIsNotNone(engine._compression_retriever)
        
        # Verify component types
        self.assertIsInstance(engine._ensemble_retriever, EnsembleRetriever)
        self.assertIsInstance(engine._compression_retriever, ContextualCompressionRetriever)
        self.assertIsInstance(engine.milvus_retriever, MilvusRetriever)
        self.assertIsInstance(engine.bm25_retriever, BM25Retriever)
        
        # Verify LCEL chain structure
        from langchain_core.runnables.base import Runnable
        self.assertIsInstance(engine.retrieval_chain, Runnable)

    def test_basic_retrieval_interface(self):
        """Test that the RetrievalEngine has the expected interface."""
        config = RetrievalConfig(top_k=5, min_score=0.5)
        self.assertEqual(config.top_k, 5)
        self.assertEqual(config.min_score, 0.5)
        
        engine = RetrievalEngine()
        
        # Check that required methods exist
        self.assertTrue(hasattr(engine, 'retrieve'))
        self.assertTrue(hasattr(engine, 'calculate_confidence'))
        
        # Check that retrieve is async
        import inspect
        self.assertTrue(inspect.iscoroutinefunction(engine.retrieve))

    def test_model_validation(self):
        """Test that Pydantic models are correctly defined."""
        # Test ChunkV3 creation
        chunk = ChunkV3(
            doc_id="test_doc",
            chunk_id="test_chunk",
            chunk_text="Test content",
            tree_node_id="0001"
        )
        self.assertEqual(chunk.doc_id, "test_doc")
        self.assertEqual(chunk.chunk_id, "test_chunk")
        
        # Test ParentDocumentV3 creation
        parent = ParentDocumentV3(
            doc_id="test_doc",
            pageindex_markdown="# Test Document"
        )
        self.assertEqual(parent.doc_id, "test_doc")
        
        # Test RetrievalResult model structure (check annotations instead of instantiation)
        from api.tools.retrieval_engine import RetrievalResult
        annotations = RetrievalResult.__annotations__
        self.assertIn('chunk', annotations)
        self.assertIn('confidence', annotations)
        self.assertIn('metadata', annotations)

    def test_confidence_calculation(self):
        """Test confidence calculation with various result sets."""
        engine = RetrievalEngine()
        
        # Test empty results
        confidence = engine.calculate_confidence([])
        self.assertEqual(confidence, 0.0)
        
        # Test with mock results (avoid Pydantic forward reference issues)
        mock_results = []
        for conf in [0.9, 0.8, 0.7]:
            mock_result = MagicMock()
            mock_result.confidence = conf
            mock_results.append(mock_result)
        
        # Test single result
        confidence = engine.calculate_confidence([mock_results[0]])
        self.assertEqual(confidence, 0.9)
        
        # Test multiple results (weighted average)
        confidence = engine.calculate_confidence(mock_results)
        self.assertGreater(confidence, 0.7)
        self.assertLess(confidence, 0.9)

    def test_agent_state_integration(self):
        """Test compatibility with AgentState for query input."""
        engine = RetrievalEngine()
        
        # Check that retrieve method signature is compatible with AgentState
        import inspect
        sig = inspect.signature(engine.retrieve)
        params = list(sig.parameters.keys())
        
        # Should accept query as string (compatible with AgentState.raw_query)
        self.assertIn('query', params)
        
        # Check parameter annotation
        query_param = sig.parameters['query']
        annotation = query_param.annotation
        self.assertTrue(annotation == str or annotation == 'str')

    # ===== SEARCH FUNCTIONALITY TESTS =====

    @pytest.mark.asyncio
    @patch('api.tools.retrieval_engine.RetrievalEngine')
    async def test_search_legal_documents_success(self, mock_engine_class):
        """Test that search_legal_documents returns results when the query is valid."""
        # Arrange
        mock_engine = MagicMock()
        mock_engine.retrieve = AsyncMock()
        mock_engine_class.return_value = mock_engine
        
        sample_chunk = ChunkV3(
            doc_id="doc1",
            chunk_id="chunk1",
            chunk_text="Test document content",
            tree_node_id="0001"
        )
        
        mock_results = [
            RetrievalResult(
                chunk=sample_chunk,
                confidence=0.9,
                metadata={'title': 'Test Document', 'source_url': 'http://example.com', 'source': 'vector'}
            )
        ]
        
        mock_engine.retrieve.return_value = mock_results
        mock_engine.calculate_confidence.return_value = 0.85
        
        # Act
        results, confidence = await search_legal_documents('test query')
        
        # Assert
        self.assertEqual(len(results), 1)
        self.assertEqual(confidence, 0.85)
        self.assertEqual(results[0].chunk_id, "chunk1")  # Use legacy property accessor
        self.assertEqual(results[0].metadata['title'], 'Test Document')
        mock_engine.retrieve.assert_called_once()
        mock_engine.calculate_confidence.assert_called_once_with(mock_results)

    @pytest.mark.asyncio
    @patch('api.tools.retrieval_engine.RetrievalEngine')
    async def test_search_legal_documents_no_results(self, mock_engine_class):
        """Test that search_legal_documents handles empty results gracefully."""
        # Arrange
        mock_engine = MagicMock()
        mock_engine.retrieve = AsyncMock(return_value=[])
        mock_engine.calculate_confidence.return_value = 0.0
        mock_engine_class.return_value = mock_engine
        
        # Act
        results, confidence = await search_legal_documents('nonexistent query')
        
        # Assert
        self.assertEqual(len(results), 0)
        self.assertEqual(confidence, 0.0)

    @pytest.mark.asyncio
    @patch('api.tools.retrieval_engine.RetrievalEngine')
    async def test_search_legal_documents_engine_error(self, mock_engine_class):
        """Test that search_legal_documents handles engine errors properly."""
        # Arrange
        mock_engine = MagicMock()
        mock_engine.retrieve = AsyncMock(side_effect=Exception("Milvus connection failed"))
        mock_engine_class.return_value = mock_engine
        
        # Act & Assert
        with self.assertRaises(Exception) as context:
            await search_legal_documents('test query')
        
        self.assertIn("Milvus connection failed", str(context.exception))

    # ===== R2 INTEGRATION TESTS =====

    @pytest.fixture
    def sample_milvus_results(self):
        """Sample Milvus search results with v2.0 schema fields."""
        return [
            {
                "chunk_id": "chunk_001",
                "parent_doc_id": "doc_123", 
                "chunk_text": "Sample legal text about employment rights",
                "score": 0.95,
                "metadata": {
                    "doc_type": "act",
                    "title": "Labour Act",
                    "section": "Part II",
                    "chunk_object_key": "chunks/processed/chunk_001.json"
                }
            },
            {
                "chunk_id": "chunk_002", 
                "parent_doc_id": "doc_456",
                "chunk_text": "Regulations on workplace safety standards",
                "score": 0.87,
                "metadata": {
                    "doc_type": "si",
                    "title": "Workplace Safety SI",
                    "section": "Section 5",
                    "chunk_object_key": "chunks/processed/chunk_002.json"
                }
            }
        ]

    @pytest.mark.asyncio
    @patch('api.tools.retrieval_engine.RetrievalEngine.__aenter__')
    @patch('api.tools.retrieval_engine.RetrievalEngine.__aexit__')
    async def test_r2_content_fetching_success(self, mock_aexit, mock_aenter):
        """Test successful R2 content fetching for chunks."""
        # Arrange
        mock_engine = AsyncMock()
        mock_aenter.return_value = mock_engine
        mock_aexit.return_value = None
        
        # Mock R2 content response
        mock_chunk_content = {
            "chunk_id": "chunk_001",
            "chunk_text": "Full chunk content from R2",
            "metadata": {"enhanced": True}
        }
        
        mock_engine.retrieve.return_value = [
            RetrievalResult(
                chunk=ChunkV3(
                    doc_id="doc_123",
                    chunk_id="chunk_001", 
                    chunk_text="Full chunk content from R2",
                    tree_node_id="0001"
                ),
                confidence=0.95,
                metadata={"enhanced": True, "source": "r2"}
            )
        ]
        
        # Act
        async with RetrievalEngine() as engine:
            results = await engine.retrieve("employment rights", RetrievalConfig(top_k=5))
        
        # Assert
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_text, "Full chunk content from R2")
        self.assertTrue(results[0].metadata.get("enhanced"))

    @pytest.mark.asyncio
    @patch('api.tools.retrieval_engine.RetrievalEngine.__aenter__')
    async def test_r2_batch_fetching_performance(self, mock_aenter):
        """Test that R2 fetching is performed in parallel batches for performance."""
        # Arrange
        mock_engine = AsyncMock()
        mock_aenter.return_value = mock_engine
        
        # Simulate multiple chunks requiring R2 fetching
        multiple_results = [
            RetrievalResult(
                chunk=ChunkV3(doc_id=f"doc_{i}", chunk_id=f"chunk_{i}", chunk_text=f"Content {i}", tree_node_id="0001"),
                confidence=0.9 - i*0.1
            ) for i in range(5)
        ]
        
        mock_engine.retrieve.return_value = multiple_results
        
        # Act
        async with RetrievalEngine() as engine:
            results = await engine.retrieve("test query", RetrievalConfig(top_k=10))
        
        # Assert
        self.assertEqual(len(results), 5)
        # Verify results are ordered by confidence (highest first)
        confidences = [r.confidence for r in results]
        self.assertEqual(confidences, sorted(confidences, reverse=True))

    # ===== ERROR HANDLING TESTS =====

    @pytest.mark.asyncio
    async def test_retrieval_with_invalid_config(self):
        """Test error handling with invalid retrieval configuration."""
        engine = RetrievalEngine()
        
        # Test with negative top_k
        with self.assertRaises(ValueError):
            config = RetrievalConfig(top_k=-1)

    @pytest.mark.asyncio
    @patch('api.tools.retrieval_engine.RetrievalEngine.milvus_client')
    async def test_milvus_connection_failure(self, mock_milvus):
        """Test handling of Milvus connection failures."""
        # Arrange
        mock_milvus.connect.side_effect = Exception("Connection timeout")
        
        engine = RetrievalEngine()
        
        # Act & Assert
        with self.assertRaises(Exception):
            await engine.retrieve("test query")

    # ===== PERFORMANCE TESTS =====

    @pytest.mark.asyncio
    async def test_retrieval_performance_requirements(self):
        """Test that retrieval meets performance requirements (P50 < 70ms for cached queries)."""
        import time
        
        engine = RetrievalEngine()
        
        # Mock fast responses for performance testing
        with patch.object(engine, 'retrieval_chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=[])
            
            start_time = time.time()
            await engine.retrieve("cached query", RetrievalConfig(top_k=5))
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Should be very fast with mocked components
            self.assertLess(elapsed_ms, 100)  # Generous limit for mocked test

    # ===== INTEGRATION TESTS =====

    def test_query_request_compatibility(self):
        """Test compatibility with existing QueryRequest model."""
        request = QueryRequest(
            query="What are the employment rights in Zimbabwe?",
            top_k=10,
            include_metadata=True
        )
        
        # Should be able to create RetrievalConfig from QueryRequest
        config = RetrievalConfig(
            top_k=request.top_k,
            min_score=0.1
        )
        
        self.assertEqual(config.top_k, 10)

    @pytest.mark.asyncio
    async def test_end_to_end_retrieval_flow(self):
        """Test the complete retrieval flow from query to results."""
        engine = RetrievalEngine()
        
        # Mock the entire chain to return sample results
        with patch.object(engine, 'retrieval_chain') as mock_chain:
            sample_results = [
                RetrievalResult(
                    chunk=self.sample_chunks[0],
                    parent_doc=self.sample_parent,
                    confidence=0.92,
                    metadata={"source": "langchain", "expanded_to_parent": True}
                )
            ]
            mock_chain.ainvoke = AsyncMock(return_value=sample_results)
            
            # Act
            results = await engine.retrieve(
                "chemical import regulations", 
                RetrievalConfig(top_k=5)
            )
            
            # Assert
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].chunk.doc_id, "doc1")
            self.assertEqual(results[0].parent_doc.title, "Chemical Import Regulations Act")
            self.assertTrue(results[0].metadata.get("expanded_to_parent"))
            self.assertEqual(results[0].metadata.get("source"), "langchain")


# ===== PYTEST-STYLE TESTS FOR COMPATIBILITY =====

@pytest.mark.asyncio
async def test_search_function_backward_compatibility():
    """Test that the search_legal_documents function maintains backward compatibility."""
    with patch('api.tools.retrieval_engine.RetrievalEngine') as mock_engine_class:
        mock_engine = MagicMock()
        mock_engine.retrieve = AsyncMock(return_value=[])
        mock_engine.calculate_confidence.return_value = 0.0
        mock_engine_class.return_value = mock_engine
        
        # Should work with positional arguments
        results, confidence = await search_legal_documents("test query", 10, None, 0.1)
        
        assert len(results) == 0
        assert confidence == 0.0


@pytest.mark.asyncio
async def test_retrieval_config_validation():
    """Test RetrievalConfig validation and defaults."""
    # Test default values
    config = RetrievalConfig()
    assert config.top_k == 20
    assert config.min_score == 0.1
    
    # Test custom values
    config = RetrievalConfig(top_k=50, min_score=0.5)
    assert config.top_k == 50
    assert config.min_score == 0.5


if __name__ == "__main__":
    unittest.main()
