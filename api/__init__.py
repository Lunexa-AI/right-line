"""Gweta API Service.

This package contains the FastAPI application and related components
for the Gweta legal information API.

Main components:
- main.py: FastAPI application with endpoints
- models.py: Pydantic models for requests and responses
- retrieval.py: RAG system for document retrieval
- composer.py: OpenAI-powered answer composition
- whatsapp.py: WhatsApp Business API integration
- analytics.py: Analytics and feedback system
"""

# Avoid importing heavy modules (e.g., FastAPI app) at package import time to
# prevent side effects when tools (like LangGraph Studio) import `api.*`.
# Intentionally do not re-export runtime objects here.
__all__ = []
