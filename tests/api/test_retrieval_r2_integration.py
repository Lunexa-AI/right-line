#!/usr/bin/env python3
"""
Test suite for R2-integrated retrieval system (Task 2.5)

Following TDD principles from .cursorrules, this test suite covers:
- Async R2 content fetching from chunk_object_keys
- Batch parallel retrieval for performance
- Error handling and resilience
- Security and authentication for document serving
- Performance monitoring and observability

Author: RightLine Team
"""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any, List

from api.tools.retrieval_engine import RetrievalEngine, RetrievalResult, RetrievalConfig
from api.models import QueryRequest


@pytest.fixture
def sample_milvus_results():
    """Sample Milvus search results with v2.0 schema fields."""
    return [
        {
            "chunk_id": "chunk_001",
            "parent_doc_id": "doc_123", 
            "chunk_object_key": "corpus/chunks/act/chunk_001.json",
            "source_document_key": "sources/act/doc_123.pdf",
            "doc_type": "act",
            "num_tokens": 150,
            "score": 0.95,
            "metadata": {"title": "Labour Act", "section": "Section 5"}
        },
        {
            "chunk_id": "chunk_002", 
            "parent_doc_id": "doc_124",
            "chunk_object_key": "corpus/chunks/act/chunk_002.json",
            "source_document_key": "sources/act/doc_124.pdf", 
            "doc_type": "act",
            "num_tokens": 200,
            "score": 0.88,
            "metadata": {"title": "Employment Act", "section": "Section 12"}
        }
    ]


@pytest.fixture  
def sample_r2_chunks():
    """Sample chunk content from R2."""
    return {
        "corpus/chunks/act/chunk_001.json": {
            "chunk_id": "chunk_001",
            "chunk_text": "Every employer shall ensure that workers receive minimum wage as prescribed by regulation.",
            "doc_id": "doc_123",
            "section_path": "Part II > Section 5",
            "metadata": {"title": "Labour Act", "section": "Section 5"}
        },
        "corpus/chunks/act/chunk_002.json": {
            "chunk_id": "chunk_002", 
            "chunk_text": "Employment contracts must specify terms of employment including working hours and conditions.",
            "doc_id": "doc_124",
            "section_path": "Part III > Section 12",
            "metadata": {"title": "Employment Act", "section": "Section 12"}
        }
    }


class TestR2ContentFetching:
    """Test R2 integration for chunk content retrieval."""
    
    @pytest.mark.asyncio
    async def test_fetch_chunk_content_from_r2_single(self, sample_r2_chunks):
        """Test fetching single chunk content from R2."""
        # Arrange
        engine = RetrievalEngine()
        chunk_key = "corpus/chunks/act/chunk_001.json"
        expected_content = sample_r2_chunks[chunk_key]
        
        # Mock R2 client response
        mock_r2_response = Mock()
        mock_r2_response.read.return_value = json.dumps(expected_content).encode('utf-8')
        
        with patch('api.retrieval.boto3.client') as mock_boto3:
            mock_r2_client = Mock()
            mock_r2_client.get_object.return_value = {'Body': mock_r2_response}
            mock_boto3.return_value = mock_r2_client
            
            # Act  
            result = await engine._fetch_chunk_content_from_r2(chunk_key)
            
            # Assert
            assert result is not None
            assert result["chunk_text"] == expected_content["chunk_text"]
            assert result["chunk_id"] == expected_content["chunk_id"]
            mock_r2_client.get_object.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_chunk_content_batch_parallel(self, sample_r2_chunks):
        """Test parallel batch fetching of multiple chunks from R2."""
        # Arrange
        engine = RetrievalEngine() 
        chunk_keys = list(sample_r2_chunks.keys())
        
        # Mock R2 responses
        mock_responses = {}
        for key, content in sample_r2_chunks.items():
            mock_response = Mock()
            mock_response.read.return_value = json.dumps(content).encode('utf-8')
            mock_responses[key] = {'Body': mock_response}
        
        with patch('api.retrieval.boto3.client') as mock_boto3:
            mock_r2_client = Mock()
            mock_r2_client.get_object.side_effect = lambda Bucket, Key, **kwargs: mock_responses[Key]
            mock_boto3.return_value = mock_r2_client
            
            # Act
            results = await engine._fetch_chunk_contents_batch(chunk_keys)
            
            # Assert
            assert len(results) == 2
            assert all(result is not None for result in results)
            assert results[0]["chunk_id"] == "chunk_001"
            assert results[1]["chunk_id"] == "chunk_002"
            # Verify parallel execution (should be called for each chunk)
            assert mock_r2_client.get_object.call_count == 2
    
    @pytest.mark.asyncio
    async def test_fetch_chunk_content_r2_error_handling(self):
        """Test error handling when R2 fetch fails."""
        # Arrange
        engine = RetrievalEngine()
        chunk_key = "corpus/chunks/act/nonexistent.json"
        
        with patch('api.retrieval.boto3.client') as mock_boto3:
            mock_r2_client = Mock()
            mock_r2_client.get_object.side_effect = Exception("S3 NoSuchKey error")
            mock_boto3.return_value = mock_r2_client
            
            # Act & Assert
            result = await engine._fetch_chunk_content_from_r2(chunk_key)
            assert result is None  # Should gracefully handle errors
    
    @pytest.mark.asyncio
    async def test_fetch_chunk_content_partial_failures(self, sample_r2_chunks):
        """Test handling partial failures in batch R2 retrieval."""
        # Arrange
        engine = RetrievalEngine()
        chunk_keys = ["corpus/chunks/act/chunk_001.json", "corpus/chunks/act/nonexistent.json"]
        
        def mock_get_object(Bucket, Key, **kwargs):
            if Key == "corpus/chunks/act/chunk_001.json":
                mock_response = Mock()
                mock_response.read.return_value = json.dumps(sample_r2_chunks[Key]).encode('utf-8')
                return {'Body': mock_response}
            else:
                raise Exception("S3 NoSuchKey error")
        
        with patch('api.retrieval.boto3.client') as mock_boto3:
            mock_r2_client = Mock()
            mock_r2_client.get_object.side_effect = mock_get_object
            mock_boto3.return_value = mock_r2_client
            
            # Act
            results = await engine._fetch_chunk_contents_batch(chunk_keys)
            
            # Assert
            assert len(results) == 2
            assert results[0] is not None  # First chunk succeeded
            assert results[1] is None       # Second chunk failed gracefully


class TestRetrievalEngineR2Integration:
    """Test RetrievalEngine integration with R2 content fetching."""
    
    @pytest.mark.asyncio
    async def test_retrieve_with_r2_content_fetching(self, sample_milvus_results, sample_r2_chunks):
        """Test full retrieval flow with R2 content fetching."""
        # Arrange
        query = "What is minimum wage?"
        config = RetrievalConfig(top_k=5)
        
        # Mock Milvus search results as RetrievalResult objects (without chunk_text)
        from api.tools.retrieval_engine import RetrievalResult
        milvus_retrieval_results = []
        for result in sample_milvus_results:
            milvus_retrieval_results.append(RetrievalResult(
                chunk_id=result["chunk_id"],
                chunk_text="",  # Empty for v2.0 schema - will be fetched from R2
                doc_id=result["parent_doc_id"],
                metadata={
                    "chunk_object_key": result["chunk_object_key"],
                    "source_document_key": result["source_document_key"],
                    "doc_type": result["doc_type"],
                    "num_tokens": result["num_tokens"],
                    **result["metadata"]
                },
                score=result["score"],
                source="vector"
            ))
        
        with patch('api.retrieval.MilvusClient') as MockMilvusClient, \
             patch('api.retrieval.EmbeddingClient') as MockEmbeddingClient, \
             patch('api.retrieval.QueryProcessor') as MockQueryProcessor:
            
            # Mock Milvus client
            mock_milvus = MockMilvusClient.return_value
            mock_milvus.connect = AsyncMock()
            mock_milvus.disconnect = AsyncMock()
            mock_milvus.search_similar_multi = AsyncMock(return_value=[milvus_retrieval_results])
            
            # Mock embedding client
            mock_embedding = MockEmbeddingClient.return_value
            mock_embedding.get_embeddings = AsyncMock(return_value=[[0.1] * 3072])
            
            # Mock query processor
            mock_processor = MockQueryProcessor.return_value
            mock_processor.normalize_query.return_value = query
            mock_processor.extract_date_context.return_value = (query, None)
            mock_processor.detect_intent.return_value = {}
            mock_processor.generate_reformulations.return_value = [query]
            
            # Mock R2 content fetching
            with patch.object(RetrievalEngine, '_fetch_chunk_contents_batch') as mock_fetch:
                mock_fetch.return_value = list(sample_r2_chunks.values())
                
                # Act
                async with RetrievalEngine() as engine:
                    results = await engine.retrieve(query, config)
                
                # Assert
                assert len(results) == 2
                assert all(isinstance(r, RetrievalResult) for r in results)
                assert all(r.chunk_text != "" for r in results)  # Content fetched from R2
                assert results[0].chunk_text == "Every employer shall ensure that workers receive minimum wage as prescribed by regulation."
                
                # Verify R2 batch fetch was called with correct chunk keys
                expected_keys = ["corpus/chunks/act/chunk_001.json", "corpus/chunks/act/chunk_002.json"]
                mock_fetch.assert_called_once_with(expected_keys)
    
    @pytest.mark.asyncio
    async def test_retrieve_r2_fallback_on_content_fetch_failure(self, sample_milvus_results):
        """Test graceful fallback when R2 content fetching fails."""
        # Arrange
        query = "What is minimum wage?"
        config = RetrievalConfig(top_k=5)
        
        with patch('api.retrieval.MilvusClient') as MockMilvusClient:
            # Mock Milvus client
            mock_milvus = MockMilvusClient.return_value
            mock_milvus.connect = AsyncMock()
            mock_milvus.disconnect = AsyncMock()
            mock_milvus.search_similar.return_value = sample_milvus_results
            
            # Mock R2 content fetching failure
            with patch.object(RetrievalEngine, '_fetch_chunk_contents_batch') as mock_fetch:
                mock_fetch.return_value = [None, None]  # All chunks failed to fetch
                
                # Act
                async with RetrievalEngine() as engine:
                    results = await engine.retrieve(query, config)
                
                # Assert - Should still return results but with empty/placeholder content
                assert len(results) == 2
                # Results should indicate content fetch failure gracefully
                assert all(isinstance(r, RetrievalResult) for r in results)


class TestPerformanceAndObservability:
    """Test performance optimizations and observability features."""
    
    @pytest.mark.asyncio
    async def test_r2_fetch_performance_logging(self, sample_r2_chunks):
        """Test that R2 fetch operations are properly logged for performance monitoring."""
        # Arrange
        engine = RetrievalEngine()
        chunk_keys = list(sample_r2_chunks.keys())
        
        with patch('api.retrieval.boto3.client'), \
             patch('api.retrieval.logger') as mock_logger:
            
            # Act
            await engine._fetch_chunk_contents_batch(chunk_keys)
            
            # Assert - Verify performance metrics are logged
            assert mock_logger.info.called
            # Should log timing information
            logged_calls = [call.args for call in mock_logger.info.call_args_list]
            timing_logged = any("R2 batch fetch" in str(call) for call in logged_calls)
            assert timing_logged
    
    @pytest.mark.asyncio
    async def test_concurrent_r2_requests_limit(self):
        """Test that concurrent R2 requests are properly limited to avoid rate limits."""
        # Arrange
        engine = RetrievalEngine()
        # Large number of chunk keys to test concurrency limiting
        chunk_keys = [f"corpus/chunks/act/chunk_{i:03d}.json" for i in range(50)]
        
        with patch('api.retrieval.boto3.client') as mock_boto3, \
             patch('asyncio.Semaphore') as mock_semaphore:
            
            mock_r2_client = Mock()
            mock_boto3.return_value = mock_r2_client
            
            # Act
            await engine._fetch_chunk_contents_batch(chunk_keys)
            
            # Assert - Should use semaphore to limit concurrent requests
            mock_semaphore.assert_called_once()


class TestSecureDocumentServing:
    """Test secure document serving endpoint (to be implemented)."""
    
    def test_document_endpoint_requires_authentication(self):
        """Test that document serving endpoint requires valid JWT token."""
        # This test will be implemented when we create the documents router
        pass
    
    def test_document_endpoint_validates_document_key(self):
        """Test that document endpoint validates document keys for security."""
        # This test will be implemented when we create the documents router
        pass
    
    def test_document_endpoint_streams_pdf_response(self):
        """Test that document endpoint properly streams PDF responses."""
        # This test will be implemented when we create the documents router
        pass


# Integration tests
class TestR2IntegrationEnd2End:
    """End-to-end integration tests for R2 retrieval system."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_query_flow_with_r2_retrieval(self):
        """Test complete query flow from API request to R2 content serving.
        
        This test requires actual R2 and Milvus connections and should only run
        when INTEGRATION_TESTS environment variable is set.
        """
        # This will be implemented for integration testing
        pass


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/api/test_retrieval_r2_integration.py -v
    pytest.main([__file__, "-v"])
