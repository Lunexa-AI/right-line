"""Debug and testing endpoints for development.

These endpoints are unprotected and provide direct access to API functionality
for testing and debugging purposes. NOT for production use.
"""

import os
import time
from typing import Dict, Any, List, Optional

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.tools.retrieval_engine import RetrievalEngine, RetrievalConfig

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Debug"])


class HealthResponse(BaseModel):
    """API health status response."""
    status: str
    timestamp: str
    version: str
    environment: Dict[str, Any]
    services: Dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def get_api_health() -> HealthResponse:
    """Get comprehensive API health status and configuration."""
    
    # Check environment variables
    env_status = {
        "milvus_configured": bool(os.getenv("MILVUS_ENDPOINT")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "r2_configured": bool(os.getenv("CLOUDFLARE_R2_S3_ENDPOINT")),
        "pageindex_configured": bool(os.getenv("PAGEINDEX_API_KEY")),
    }
    
    # Test services
    services = {}
    
    # Test Milvus connection
    try:
        from pymilvus import connections, Collection
        collection_name = os.getenv("MILVUS_COLLECTION_NAME", "legal_chunks_v3")
        
        connections.connect(
            alias="health_check",
            uri=os.getenv("MILVUS_ENDPOINT"),
            token=os.getenv("MILVUS_TOKEN")
        )
        
        collection = Collection(collection_name, using="health_check")
        entity_count = collection.num_entities
        
        services["milvus"] = {
            "status": "connected",
            "collection": collection_name,
            "entities": entity_count
        }
        
        connections.disconnect("health_check")
        
    except Exception as e:
        services["milvus"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Test R2 connection
    try:
        import boto3
        r2_client = boto3.client(
            's3',
            endpoint_url=os.getenv("CLOUDFLARE_R2_S3_ENDPOINT"),
            aws_access_key_id=os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
        )
        
        # Test bucket access
        bucket = os.getenv("CLOUDFLARE_R2_BUCKET_NAME", "gweta-prod-documents")
        paginator = r2_client.get_paginator('list_objects_v2')
        
        # Count objects in key prefixes
        chunk_count = 0
        doc_count = 0
        
        # Count chunks
        for page in paginator.paginate(Bucket=bucket, Prefix="corpus/chunks/", MaxKeys=1000):
            chunk_count += len(page.get('Contents', []))
            
        # Count docs  
        for page in paginator.paginate(Bucket=bucket, Prefix="corpus/docs/", MaxKeys=1000):
            doc_count += len(page.get('Contents', []))
        
        services["r2"] = {
            "status": "connected",
            "bucket": bucket,
            "chunks": chunk_count,
            "docs": doc_count
        }
        
    except Exception as e:
        services["r2"] = {
            "status": "error", 
            "error": str(e)
        }
    
    # Overall status
    all_services_ok = all(s.get("status") == "connected" for s in services.values())
    overall_status = "healthy" if all_services_ok and all(env_status.values()) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        version="3.0-pageindex",
        environment=env_status,
        services=services
    )
