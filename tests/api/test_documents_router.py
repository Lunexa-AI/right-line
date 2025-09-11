#!/usr/bin/env python3
"""
Test suite for secure document serving router (Task 2.5)

Following TDD principles from .cursorrules, this test suite covers:
- JWT authentication enforcement
- Secure document key validation  
- PDF streaming from R2
- Error handling and security controls
- Performance monitoring and audit logging

Author: RightLine Team
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from io import BytesIO

from api.routers.documents import router, R2DocumentClient
from api.auth import User, get_current_user


@pytest.fixture
def mock_authenticated_user():
    """Mock authenticated user for testing."""
    return User(
        uid="test_user_123",
        email="test@example.com",
        firebase_claims={"email_verified": True}
    )


@pytest.fixture 
def sample_pdf_content():
    """Sample PDF content for testing."""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF"


class TestDocumentKeyValidation:
    """Test document key validation and security controls."""
    
    def test_validate_document_key_valid_sources(self):
        """Test that valid source document keys are accepted."""
        client = R2DocumentClient()
        
        valid_keys = [
            "sources/act/labour_act_2023.pdf",
            "sources/judgment/case_001.pdf", 
            "corpus/docs/act/doc_123.json",
            "corpus/docs/judgment/judgment_456.json"
        ]
        
        for key in valid_keys:
            assert client._validate_document_key(key), f"Valid key rejected: {key}"
    
    def test_validate_document_key_path_traversal_prevention(self):
        """Test that path traversal attacks are prevented."""
        client = R2DocumentClient()
        
        malicious_keys = [
            "../../../etc/passwd",
            "sources/../../../secret.pdf",
            "sources/act/../../admin/secret.pdf", 
            "/sources/act/document.pdf",  # Absolute path
            "sources/act/../../../database.db"
        ]
        
        for key in malicious_keys:
            assert not client._validate_document_key(key), f"Malicious key accepted: {key}"
    
    def test_validate_document_key_invalid_prefixes(self):
        """Test that only allowed prefixes are accepted."""
        client = R2DocumentClient()
        
        invalid_keys = [
            "admin/config.pdf",
            "secrets/api_keys.json",
            "backup/database.sql",
            "temp/upload.pdf"
        ]
        
        for key in invalid_keys:
            assert not client._validate_document_key(key), f"Invalid prefix accepted: {key}"
    
    def test_validate_document_key_file_type_restrictions(self):
        """Test that only PDFs are allowed in sources/ directory."""
        client = R2DocumentClient()
        
        # Valid PDF
        assert client._validate_document_key("sources/act/document.pdf")
        
        # Invalid file types in sources/
        invalid_source_files = [
            "sources/act/document.exe",
            "sources/act/script.sh", 
            "sources/act/config.json",
            "sources/act/malware.bat"
        ]
        
        for key in invalid_source_files:
            assert not client._validate_document_key(key), f"Non-PDF source file accepted: {key}"


class TestDocumentServing:
    """Test secure document serving functionality."""
    
    @pytest.mark.asyncio
    async def test_get_document_stream_success(self, sample_pdf_content):
        """Test successful document streaming from R2."""
        client = R2DocumentClient()
        document_key = "sources/act/test_document.pdf"
        
        # Mock R2 responses
        mock_head_response = {
            'ContentLength': len(sample_pdf_content),
            'ContentType': 'application/pdf',
            'LastModified': '2023-01-01T00:00:00Z'
        }
        
        mock_get_response = {
            'Body': BytesIO(sample_pdf_content)
        }
        
        with patch('api.routers.documents.boto3.client') as mock_boto3:
            mock_r2_client = Mock()
            mock_r2_client.head_object.return_value = mock_head_response
            mock_r2_client.get_object.return_value = mock_get_response
            mock_boto3.return_value = mock_r2_client
            
            # Act
            response = await client.get_document_stream(document_key)
            
            # Assert
            assert response is not None
            assert response.media_type == 'application/pdf'
            assert 'Content-Disposition' in response.headers
            assert 'Cache-Control' in response.headers
    
    @pytest.mark.asyncio  
    async def test_get_document_stream_not_found(self):
        """Test handling when document doesn't exist in R2."""
        client = R2DocumentClient()
        document_key = "sources/act/nonexistent.pdf"
        
        with patch('api.routers.documents.boto3.client') as mock_boto3:
            mock_r2_client = Mock()
            mock_r2_client.head_object.side_effect = Exception("NoSuchKey")
            mock_boto3.return_value = mock_r2_client
            
            # Act
            response = await client.get_document_stream(document_key)
            
            # Assert
            assert response is None
    
    @pytest.mark.asyncio
    async def test_get_document_stream_oversized_file(self):
        """Test that oversized documents are rejected for security."""
        client = R2DocumentClient()
        document_key = "sources/act/huge_document.pdf"
        
        # Mock response with file larger than MAX_DOCUMENT_SIZE
        mock_head_response = {
            'ContentLength': 100_000_000,  # 100MB (over 50MB limit)
            'ContentType': 'application/pdf'
        }
        
        with patch('api.routers.documents.boto3.client') as mock_boto3:
            mock_r2_client = Mock()
            mock_r2_client.head_object.return_value = mock_head_response
            mock_boto3.return_value = mock_r2_client
            
            # Act
            response = await client.get_document_stream(document_key)
            
            # Assert  
            assert response is None  # Should reject oversized files


class TestDocumentRouterEndpoints:
    """Test FastAPI document router endpoints with authentication."""
    
    def test_serve_document_requires_authentication(self):
        """Test that document endpoint requires valid JWT token."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Act - request without authentication
        response = client.get("/v1/documents/sources/act/test.pdf")
        
        # Assert
        assert response.status_code == 401  # Unauthorized
    
    def test_serve_document_invalid_key_returns_404(self, mock_authenticated_user):
        """Test that invalid document keys return 404."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        
        app = FastAPI()
        
        # Override the dependency for testing
        def override_get_current_user():
            return mock_authenticated_user
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.include_router(router)
        client = TestClient(app)
        
        with patch('api.routers.documents._r2_client') as mock_client:
            mock_client.get_document_stream.return_value = None  # Simulate not found
            
            # Act
            response = client.get("/v1/documents/invalid/../path/traversal.pdf")
            
            # Assert
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_document_metadata_success(self, mock_authenticated_user):
        """Test successful metadata retrieval."""
        mock_metadata = {
            "document_key": "sources/act/test.pdf",
            "content_type": "application/pdf", 
            "content_length": 1024,
            "last_modified": "2023-01-01T00:00:00Z",
            "etag": "abc123"
        }
        
        with patch('api.routers.documents.get_current_user', return_value=mock_authenticated_user), \
             patch('api.routers.documents._r2_client') as mock_client:
            
            # Mock the internal R2 client call
            mock_r2 = Mock()
            mock_r2.head_object.return_value = {
                'ContentLength': 1024,
                'ContentType': 'application/pdf',
                'LastModified': '2023-01-01T00:00:00Z',
                'ETag': 'abc123'
            }
            mock_client._get_client.return_value = mock_r2
            mock_client._validate_document_key.return_value = True
            
            from fastapi.testclient import TestClient
            from fastapi import FastAPI
            
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            
            # Act  
            response = client.get("/v1/documents/sources/act/test.pdf/metadata")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["document_key"] == "sources/act/test.pdf"
            assert data["content_type"] == "application/pdf"
            assert data["content_length"] == 1024


class TestSecurityAndAuditLogging:
    """Test security features and audit logging."""
    
    @pytest.mark.asyncio
    async def test_document_access_logged_for_audit(self, mock_authenticated_user):
        """Test that document access is properly logged for security audit."""
        with patch('api.routers.documents.get_current_user', return_value=mock_authenticated_user), \
             patch('api.routers.documents.logger') as mock_logger, \
             patch('api.routers.documents._r2_client') as mock_client:
            
            mock_client.get_document_stream.return_value = None  # Simulate not found
            
            from fastapi.testclient import TestClient
            from fastapi import FastAPI
            
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            
            # Act
            response = client.get("/v1/documents/sources/act/test.pdf")
            
            # Assert
            assert response.status_code == 404
            
            # Verify audit logging
            assert mock_logger.info.called or mock_logger.warning.called
            # Should log both the request and the denial
            log_calls = mock_logger.info.call_args_list + mock_logger.warning.call_args_list
            assert len(log_calls) >= 1
    
    def test_r2_client_validates_configuration_on_init(self):
        """Test that R2 client validates configuration during initialization."""
        with patch('api.routers.documents.R2_ENDPOINT', None):
            with pytest.raises(ValueError, match="R2 configuration incomplete"):
                R2DocumentClient()


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/api/test_documents_router.py -v
    pytest.main([__file__, "-v"])
