"""
Secure document serving endpoint for RightLine API.

This router implements Task 2.5: secure document serving from R2 storage
with user authentication and proper security controls.

Key features:
- JWT-based authentication using Firebase Auth
- Secure PDF streaming from R2 storage  
- Proper error handling and logging
- Performance optimizations for document serving
- Security-first design with input validation

Author: RightLine Team
"""

from __future__ import annotations

import os
import time
from typing import Optional

import boto3
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from api.auth import User, get_current_user
from libs.common.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter()

# R2 configuration from environment  
R2_ENDPOINT = os.environ.get("R2_ENDPOINT") or os.environ.get("CLOUDFLARE_R2_S3_ENDPOINT")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID") or os.environ.get("CLOUDFLARE_R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY") or os.environ.get("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME") or os.environ.get("CLOUDFLARE_R2_BUCKET_NAME", "gweta-prod-documents")

# Document serving configuration
MAX_DOCUMENT_SIZE = int(os.environ.get("MAX_DOCUMENT_SIZE", "50_000_000"))  # 50MB max
ALLOWED_DOCUMENT_PREFIXES = [
    "sources/",  # Source PDFs
    "corpus/docs/",  # Parent documents (for small-to-big expansion)
]


class R2DocumentClient:
    """Async R2 client for document serving with security and performance optimizations."""
    
    def __init__(self):
        self._client = None
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate R2 configuration on initialization."""
        if not all([R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY]):
            raise ValueError("R2 configuration incomplete. Check R2_* environment variables.")
    
    def _get_client(self):
        """Get or create R2 client."""
        if self._client is None:
            self._client = boto3.client(
                's3',
                endpoint_url=R2_ENDPOINT,
                aws_access_key_id=R2_ACCESS_KEY,
                aws_secret_access_key=R2_SECRET_KEY,
                region_name='auto'  # R2 uses 'auto' region
            )
        return self._client
    
    def _validate_document_key(self, document_key: str) -> bool:
        """Validate document key for security.
        
        Args:
            document_key: The document key to validate
            
        Returns:
            True if key is valid and safe, False otherwise
        """
        # Security checks
        if not document_key:
            return False
        
        # Prevent path traversal attacks
        if ".." in document_key or document_key.startswith("/"):
            logger.warning("Rejected document key with path traversal", key=document_key)
            return False
        
        # Only allow specific prefixes
        if not any(document_key.startswith(prefix) for prefix in ALLOWED_DOCUMENT_PREFIXES):
            logger.warning("Rejected document key with invalid prefix", key=document_key, allowed_prefixes=ALLOWED_DOCUMENT_PREFIXES)
            return False
        
        # Only allow PDF files for source documents
        if document_key.startswith("sources/") and not document_key.endswith(".pdf"):
            logger.warning("Rejected non-PDF file in sources", key=document_key)
            return False
        
        return True
    
    async def get_document_stream(self, document_key: str) -> Optional[StreamingResponse]:
        """Get document as streaming response from R2.
        
        Args:
            document_key: The R2 object key for the document
            
        Returns:
            StreamingResponse for streaming the document, or None if error
        """
        # Validate document key
        if not self._validate_document_key(document_key):
            return None
        
        try:
            client = self._get_client()
            
            # Check if document exists and get metadata
            try:
                head_response = client.head_object(Bucket=R2_BUCKET_NAME, Key=document_key)
                content_length = head_response.get('ContentLength', 0)
                content_type = head_response.get('ContentType', 'application/pdf')
                
                # Security check: reject oversized documents
                if content_length > MAX_DOCUMENT_SIZE:
                    logger.warning(
                        "Document too large", 
                        key=document_key,
                        size=content_length,
                        max_size=MAX_DOCUMENT_SIZE
                    )
                    return None
                    
            except Exception as e:
                logger.warning("Document not found or inaccessible", key=document_key, error=str(e))
                return None
            
            # Stream document content
            def generate_chunks():
                try:
                    response = client.get_object(Bucket=R2_BUCKET_NAME, Key=document_key)
                    
                    # Stream in chunks for memory efficiency
                    chunk_size = 8192  # 8KB chunks
                    while True:
                        chunk = response['Body'].read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                        
                except Exception as e:
                    logger.error("Error streaming document", key=document_key, error=str(e))
                    # Don't yield anything on error - let FastAPI handle it
            
            return StreamingResponse(
                generate_chunks(),
                media_type=content_type,
                headers={
                    "Content-Disposition": f"inline; filename=\"{document_key.split('/')[-1]}\"",
                    "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                    "X-Document-Key": document_key  # For debugging
                }
            )
            
        except Exception as e:
            logger.error("Unexpected error in document streaming", key=document_key, error=str(e))
            return None


# Singleton R2 client instance
_r2_client = R2DocumentClient()


@router.get("/v1/documents/{document_key:path}", 
           summary="Serve legal documents securely",
           description="Stream PDF documents from secure storage with user authentication",
           tags=["Documents"])
async def serve_document(
    document_key: str,
    current_user: User = Depends(get_current_user)
) -> StreamingResponse:
    """
    Serve a legal document from secure R2 storage.
    
    This endpoint implements secure document serving as specified in Task 2.5.
    All requests must include a valid JWT token for authentication.
    
    Args:
        document_key: The R2 object key for the document (e.g., 'sources/act/doc_123.pdf')
        current_user: Authenticated user from JWT token
        
    Returns:
        StreamingResponse: PDF document stream
        
    Raises:
        HTTPException: 401 for authentication failure, 403 for access denied, 404 for not found
        
    Security features:
    - JWT authentication required
    - Path traversal attack prevention
    - File type validation
    - Size limits (50MB max)
    - Audit logging
        
    Example:
        ```bash
        curl -H "Authorization: Bearer <jwt_token>" \\
             https://api.gweta.co/v1/documents/sources/act/labour_act_2023.pdf
        ```
    """
    start_time = time.time()
    
    logger.info(
        "Document access request",
        user_id=current_user.uid,
        document_key=document_key,
        user_email=getattr(current_user, 'email', 'unknown')
    )
    
    try:
        # Get document stream from R2
        stream_response = await _r2_client.get_document_stream(document_key)
        
        if stream_response is None:
            # Log access attempt for security monitoring
            logger.warning(
                "Document access denied or not found",
                user_id=current_user.uid,
                document_key=document_key,
                user_email=getattr(current_user, 'email', 'unknown')
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found or access denied: {document_key}"
            )
        
        # Log successful access for audit trail
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(
            "Document served successfully",
            user_id=current_user.uid,
            document_key=document_key,
            elapsed_ms=elapsed_ms
        )
        
        return stream_response
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        # Log error for monitoring
        logger.error(
            "Document serving error",
            user_id=current_user.uid,
            document_key=document_key,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while serving document"
        )


@router.get("/v1/documents/{document_key:path}/metadata",
           summary="Get document metadata",
           description="Get metadata for a document without downloading the content",
           tags=["Documents"])  
async def get_document_metadata(
    document_key: str,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Get metadata for a document without downloading the full content.
    
    Args:
        document_key: The R2 object key for the document
        current_user: Authenticated user from JWT token
        
    Returns:
        Dict with document metadata (size, type, last modified, etc.)
        
    Raises:
        HTTPException: 401 for authentication failure, 404 for not found
    """
    logger.info(
        "Document metadata request",
        user_id=current_user.uid,
        document_key=document_key
    )
    
    try:
        # Validate document key
        if not _r2_client._validate_document_key(document_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invalid document key: {document_key}"
            )
        
        # Get document metadata from R2
        client = _r2_client._get_client()
        head_response = client.head_object(Bucket=R2_BUCKET_NAME, Key=document_key)
        
        metadata = {
            "document_key": document_key,
            "content_type": head_response.get('ContentType', 'application/pdf'),
            "content_length": head_response.get('ContentLength', 0),
            "last_modified": head_response.get('LastModified', '').isoformat() if head_response.get('LastModified') else None,
            "etag": head_response.get('ETag', ''),
        }
        
        # Add custom metadata if available
        custom_metadata = head_response.get('Metadata', {})
        if custom_metadata:
            metadata['custom_metadata'] = custom_metadata
        
        logger.info(
            "Document metadata retrieved",
            user_id=current_user.uid,
            document_key=document_key,
            content_length=metadata['content_length']
        )
        
        return metadata
        
    except client.exceptions.NoSuchKey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_key}"
        )
    except Exception as e:
        logger.error(
            "Error retrieving document metadata",
            user_id=current_user.uid,
            document_key=document_key,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving metadata"
        )
