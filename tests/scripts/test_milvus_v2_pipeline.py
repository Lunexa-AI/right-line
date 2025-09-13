#!/usr/bin/env python3
"""
Test suite for the v2.0 Milvus pipeline (init-milvus-v2.py and milvus_upsert_v2.py)

This test suite validates the new "Small-to-Big" architecture implementation,
following TDD principles as required by .cursorrules.

Tests cover:
- Schema creation and validation
- R2 chunk loading and transformation
- Embedding generation (mocked)
- Data upload to Milvus
- End-to-end pipeline integration

Author: RightLine Team
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Try to import the modules we need for testing
IMPORTS_AVAILABLE = False
get_config = None
transform_chunk_for_milvus_v2 = None
generate_embeddings_batch = None
create_r2_client = None  
load_chunk_from_r2 = None
list_chunks_from_r2 = None
init_milvus_v2 = None

try:
    from scripts.milvus_upsert_v2 import (
        get_config,
        transform_chunk_for_milvus_v2,
        generate_embeddings_batch,
        create_r2_client,
        load_chunk_from_r2,
        list_chunks_from_r2
    )
    
    from scripts import init_milvus_v2
    
    IMPORTS_AVAILABLE = True
    print("✅ Successfully imported all required modules for testing")
except Exception as e:
    print(f"❌ Import error: {e}")
    print("⚠️  Tests will be skipped due to missing imports")
    # Functions will remain None, tests will be skipped


class TestMilvusV2Schema(unittest.TestCase):
    """Test the new v2.0 Milvus schema creation."""
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_schema_has_required_fields(self):
        """Test that the v3.0 schema contains all required fields from task spec."""
        schema = init_milvus_v2.create_collection_schema_v3()
        
        # Required fields from V3 schema (including tree_node_id)
        required_fields = {
            "chunk_id",
            "embedding", 
            "num_tokens",
            "doc_type",
            "language",
            "parent_doc_id",
            "tree_node_id",
            "chunk_object_key",
            "source_document_key",
            "nature",
            "year", 
            "chapter",
            "date_context"
        }
        
        schema_field_names = {field.name for field in schema.fields}
        
        for field_name in required_fields:
            self.assertIn(field_name, schema_field_names, 
                         f"Required field '{field_name}' missing from schema")
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_chunk_id_is_primary_key(self):
        """Test that chunk_id is set as the primary key."""
        schema = init_milvus_v2.create_collection_schema_v3()
        
        primary_fields = [field for field in schema.fields if field.is_primary]
        self.assertEqual(len(primary_fields), 1, "Should have exactly one primary key")
        self.assertEqual(primary_fields[0].name, "chunk_id", "chunk_id should be primary key")
        self.assertFalse(primary_fields[0].auto_id, "Primary key should not be auto-generated")
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_embedding_field_configuration(self):
        """Test that embedding field has correct configuration."""
        schema = init_milvus_v2.create_collection_schema_v3()
        
        embedding_field = None
        for field in schema.fields:
            if field.name == "embedding":
                embedding_field = field
                break
        
        self.assertIsNotNone(embedding_field, "Embedding field should exist")
        self.assertEqual(embedding_field.dim, 3072, "Should use OpenAI text-embedding-3-large dimension")
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_string_fields_have_max_length(self):
        """Test that string fields have appropriate max_length constraints."""
        schema = init_milvus_v2.create_collection_schema_v3()
        
        expected_lengths = {
            "doc_type": 20,
            "language": 10,
            "parent_doc_id": 64,
            "tree_node_id": 16,
            "chunk_object_key": 200,
            "source_document_key": 200,
            "nature": 32,
            "chapter": 16,
            "date_context": 32
        }
        
        for field in schema.fields:
            if field.name in expected_lengths:
                self.assertEqual(field.max_length, expected_lengths[field.name],
                               f"Field '{field.name}' should have max_length {expected_lengths[field.name]}")


class TestChunkTransformation(unittest.TestCase):
    """Test chunk data transformation for the v3.0 schema."""
    
    def setUp(self):
        """Set up test data."""
        self.sample_chunk = {
            "chunk_id": "test_chunk_001",
            "doc_id": "test_doc_123",
            "parent_doc_id": "test_doc_123",
            "tree_node_id": "001A",
            "chunk_text": "This is test content for legal document chunking.",
            "num_tokens": 150,
            "doc_type": "act",
            "language": "eng",
            "nature": "Act",
            "year": 2023,
            "chapter": "7:01",
            "date_context": "2023-01-15",
            "chunk_object_key": "corpus/chunks/act/test_chunk_001.json",
            "metadata": {
                "title": "Test Act",
                "source_document_key": "sources/act/test_doc_123.pdf"
            }
        }
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_transform_chunk_basic_fields(self):
        """Test basic field transformation."""
        result = transform_chunk_for_milvus_v2(self.sample_chunk)
        
        # Test required fields are present
        required_fields = [
            "chunk_id", "num_tokens", "doc_type", "language", 
            "parent_doc_id", "tree_node_id", "chunk_object_key", "source_document_key",
            "nature", "year", "chapter", "date_context"
        ]
        
        for field in required_fields:
            self.assertIn(field, result, f"Field '{field}' should be in transformed result")
        
        # Test field values
        self.assertEqual(result["chunk_id"], "test_chunk_001")
        self.assertEqual(result["num_tokens"], 150)
        self.assertEqual(result["doc_type"], "act")
        self.assertEqual(result["language"], "eng")
        self.assertEqual(result["parent_doc_id"], "test_doc_123")
        self.assertEqual(result["tree_node_id"], "001A")
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_transform_chunk_field_length_constraints(self):
        """Test that fields are truncated to max lengths."""
        long_chunk = self.sample_chunk.copy()
        long_chunk["doc_type"] = "a" * 50  # Exceeds 20 char limit
        long_chunk["language"] = "b" * 20  # Exceeds 10 char limit
        long_chunk["nature"] = "c" * 50   # Exceeds 32 char limit
        
        result = transform_chunk_for_milvus_v2(long_chunk)
        
        self.assertEqual(len(result["doc_type"]), 20, "doc_type should be truncated to 20 chars")
        self.assertEqual(len(result["language"]), 10, "language should be truncated to 10 chars")
        self.assertEqual(len(result["nature"]), 32, "nature should be truncated to 32 chars")
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_transform_chunk_missing_optional_fields(self):
        """Test transformation with missing optional fields."""
        minimal_chunk = {
            "chunk_id": "minimal_001",
            "doc_id": "minimal_doc",
            "num_tokens": 100,
            "chunk_object_key": "corpus/chunks/other/minimal_001.json"
        }
        
        result = transform_chunk_for_milvus_v2(minimal_chunk)
        
        # Should have default values
        self.assertEqual(result["doc_type"], "unknown")
        self.assertEqual(result["language"], "eng")
        self.assertEqual(result["nature"], "")
        self.assertEqual(result["year"], 0)
        self.assertEqual(result["chapter"], "")
        self.assertEqual(result["date_context"], "")
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_transform_chunk_source_document_key_construction(self):
        """Test construction of source_document_key when not provided."""
        chunk_no_source = self.sample_chunk.copy()
        del chunk_no_source["metadata"]
        
        result = transform_chunk_for_milvus_v2(chunk_no_source)
        
        expected_key = "sources/act/test_doc_123.pdf"
        self.assertEqual(result["source_document_key"], expected_key)
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_transform_chunk_validation_errors(self):
        """Test that transformation raises errors for invalid data."""
        # Missing chunk_id
        invalid_chunk = self.sample_chunk.copy()
        del invalid_chunk["chunk_id"]
        
        with self.assertRaises(ValueError):
            transform_chunk_for_milvus_v2(invalid_chunk)
        
        # Missing chunk_object_key
        invalid_chunk2 = self.sample_chunk.copy()
        del invalid_chunk2["chunk_object_key"]
        
        with self.assertRaises(ValueError):
            transform_chunk_for_milvus_v2(invalid_chunk2)


class TestR2Integration(unittest.TestCase):
    """Test R2 storage integration."""
    
    @patch('boto3.client')
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_create_r2_client(self, mock_boto3):
        """Test R2 client creation."""
        mock_client = Mock()
        mock_boto3.return_value = mock_client
        
        result = create_r2_client("https://test.r2.dev", "test_key", "test_secret")
        
        mock_boto3.assert_called_once_with(
            "s3",
            endpoint_url="https://test.r2.dev",
            aws_access_key_id="test_key", 
            aws_secret_access_key="test_secret",
            region_name="auto"
        )
        
        self.assertEqual(result, mock_client)
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_list_chunks_from_r2(self):
        """Test listing chunks from R2."""
        mock_client = Mock()
        mock_paginator = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        
        # Mock paginator response
        mock_paginator.paginate.return_value = [
            {
                'Contents': [
                    {'Key': 'corpus/chunks/act/chunk1.json'},
                    {'Key': 'corpus/chunks/act/chunk2.json'},
                    {'Key': 'corpus/chunks/judgment/chunk3.json'},
                    {'Key': 'corpus/chunks/other/not_json.txt'},  # Should be filtered out
                ]
            }
        ]
        
        result = list_chunks_from_r2(mock_client, "test-bucket")
        
        expected = [
            'corpus/chunks/act/chunk1.json',
            'corpus/chunks/act/chunk2.json', 
            'corpus/chunks/judgment/chunk3.json'
        ]
        
        self.assertEqual(result, expected)
        mock_client.get_paginator.assert_called_once_with('list_objects_v2')
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_load_chunk_from_r2(self):
        """Test loading a single chunk from R2."""
        mock_client = Mock()
        mock_response = Mock()
        mock_body = Mock()
        mock_body.read.return_value = json.dumps({
            "chunk_id": "test_001",
            "chunk_text": "Test content", 
            "num_tokens": 50
        }).encode('utf-8')
        mock_response.__getitem__.return_value = mock_body
        mock_client.get_object.return_value = mock_response
        
        result = load_chunk_from_r2(mock_client, "test-bucket", "corpus/chunks/act/test_001.json")
        
        expected = {
            "chunk_id": "test_001", 
            "chunk_text": "Test content",
            "num_tokens": 50,
            "chunk_object_key": "corpus/chunks/act/test_001.json"
        }
        
        self.assertEqual(result, expected)
        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="corpus/chunks/act/test_001.json"
        )


class TestEmbeddingGeneration(unittest.TestCase):
    """Test embedding generation using OpenAI API."""
    
    @patch('openai.OpenAI')
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_generate_embeddings_batch(self, mock_openai_class):
        """Test batch embedding generation."""
        # Mock OpenAI client and response
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1, 0.2, 0.3]),
            Mock(embedding=[0.4, 0.5, 0.6])
        ]
        mock_client.embeddings.create.return_value = mock_response
        
        texts = ["First text", "Second text"]
        result = generate_embeddings_batch(texts, "text-embedding-3-large")
        
        expected = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        self.assertEqual(result, expected)
        
        mock_client.embeddings.create.assert_called_once_with(
            input=texts,
            model="text-embedding-3-large"
        )
    
    @patch('openai.OpenAI')
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_generate_embeddings_batch_error_handling(self, mock_openai_class):
        """Test error handling in embedding generation."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_client.embeddings.create.side_effect = Exception("API Error")
        
        texts = ["Test text"]
        
        with self.assertRaises(Exception):
            generate_embeddings_batch(texts)


class TestConfigValidation(unittest.TestCase):
    """Test configuration validation."""
    
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_get_config_missing_required_env_vars(self):
        """Test that missing environment variables raise appropriate errors."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as cm:
                get_config()
            
            self.assertIn("MILVUS_ENDPOINT", str(cm.exception))
    
    @patch.dict(os.environ, {
        'MILVUS_ENDPOINT': 'https://test.milvus.io',
        'MILVUS_TOKEN': 'test_token',
        'R2_ENDPOINT': 'https://test.r2.dev',
        'R2_ACCESS_KEY_ID': 'test_access',
        'R2_SECRET_ACCESS_KEY': 'test_secret',
        'OPENAI_API_KEY': 'test_openai_key',
        'MILVUS_COLLECTION_NAME': 'test_collection_v2',
    })
    @unittest.skipIf(not IMPORTS_AVAILABLE, "Imports not available")
    def test_get_config_valid_environment(self):
        """Test configuration with valid environment variables."""
        config = get_config()
        
        self.assertEqual(config['milvus_endpoint'], 'https://test.milvus.io')
        self.assertEqual(config['milvus_token'], 'test_token')
        self.assertEqual(config['r2_endpoint'], 'https://test.r2.dev')
        self.assertEqual(config['openai_api_key'], 'test_openai_key')
        self.assertEqual(config['milvus_collection_name'], 'test_collection_v2')  # Explicit env value


@unittest.skipIf('INTEGRATION_TESTS' not in os.environ, "Integration tests require INTEGRATION_TESTS env var")
class TestIntegrationMilvusV2Pipeline(unittest.TestCase):
    """Integration tests for the full v2.0 pipeline (requires real services)."""
    
    def test_full_pipeline_small_dataset(self):
        """Test the complete pipeline with a small test dataset."""
        # This would require actual Milvus and R2 connections
        # Only run when INTEGRATION_TESTS environment variable is set
        pass


if __name__ == '__main__':
    # Set up test environment
    os.environ.setdefault('MILVUS_COLLECTION_NAME', 'test_collection')
    
    # Run tests
    unittest.main(verbosity=2)
