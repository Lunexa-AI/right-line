"""RightLine API Service.

This package contains the FastAPI application and related components
for the RightLine legal information API.

Main components:
- main.py: FastAPI application with endpoints
- models.py: Pydantic models for requests and responses
- retrieval.py: RAG system for document retrieval
- composer.py: OpenAI-powered answer composition
- whatsapp.py: WhatsApp Business API integration
- analytics.py: Analytics and feedback system
"""

from api.main import app, create_app
from api.models import QueryRequest, QueryResponse, HealthResponse

__all__ = [
    "app",
    "create_app", 
    "QueryRequest",
    "QueryResponse",
    "HealthResponse",
]
