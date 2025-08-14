"""RightLine API Service.

This package contains the FastAPI application and related components
for the RightLine legal information API.

Main components:
- main.py: FastAPI application with endpoints
- models.py: Pydantic models for requests and responses
- responses.py: Hardcoded legal responses for MVP
"""

from services.api.main import app, create_app
from services.api.models import QueryRequest, QueryResponse, HealthResponse

__all__ = [
    "app",
    "create_app", 
    "QueryRequest",
    "QueryResponse",
    "HealthResponse",
]
