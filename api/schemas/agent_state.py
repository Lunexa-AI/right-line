"""Agent State schema for the Gweta agentic system.

This module defines the core state object that flows through the LangGraph orchestrator.
The state tracks the complete lifecycle of a query from raw input to final response.

Follows .cursorrules principles: Pydantic for data integrity, explicit versioning, clean contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Literal, Optional, Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Citation information for retrieved sources."""
    
    doc_key: str = Field(description="Document identifier")
    page: Optional[int] = Field(default=None, description="Page number if available")
    snippet_range: Optional[tuple[int, int]] = Field(default=None, description="Character range of snippet")
    confidence: float = Field(ge=0.0, le=1.0, description="Citation confidence score")
    title: Optional[str] = Field(default=None, description="Document title")
    section_path: Optional[str] = Field(default=None, description="Hierarchical section path")


class AgentState(BaseModel):
    """Core state object for the agentic query processing pipeline.
    
    This state flows through all nodes in the LangGraph orchestrator,
    tracking the complete lifecycle of a user query.
    """
    
    # Versioning and tracing
    state_version: Literal["v1"] = Field(default="v1", description="State schema version")
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Unique trace identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="State creation timestamp")
    request_id: Optional[str] = Field(default=None, description="Per-request identifier")
    
    # User context
    user_id: str = Field(description="Firebase user ID")
    session_id: str = Field(description="Session identifier")
    
    # Initial input
    raw_query: str = Field(description="Original user query")
    deadline_ms: Optional[int] = Field(default=None, description="Soft deadline budget in milliseconds")
    session_history_ids: List[str] = Field(default_factory=list, description="Recent message IDs for context")
    user_profile_key: Optional[str] = Field(default=None, description="R2 key for user's long-term profile")
    jurisdiction: Optional[str] = Field(default=None, description="Legal jurisdiction (e.g., 'ZW')")
    date_context: Optional[str] = Field(default=None, description="Temporal context (e.g., 'as_of=2024-01-01')")
    
    # Intent routing
    intent: Optional[Literal["rag_qa", "conversational", "summarize", "disambiguate"]] = Field(
        default=None, description="Classified user intent"
    )
    intent_confidence: Optional[float] = Field(default=None, description="Confidence score for intent classification")
    complexity: Optional[Literal["simple", "moderate", "complex", "expert"]] = Field(
        default=None, description="Query complexity assessment"
    )
    user_type: Optional[Literal["professional", "citizen"]] = Field(
        default=None, description="Detected user type for persona adaptation"
    )
    reasoning_framework: Optional[str] = Field(
        default=None, description="Selected reasoning framework (irac, constitutional, statutory, precedent)"
    )
    legal_areas: List[str] = Field(default_factory=list, description="Legal areas covered in query")
    
    # Query processing
    rewritten_query: Optional[str] = Field(default=None, description="History-aware rewritten query")
    hypothetical_docs: List[str] = Field(default_factory=list, description="Multi-HyDE generated hypotheticals")
    sub_questions: List[str] = Field(default_factory=list, description="Decomposed sub-questions")
    retrieval_strategy: Optional[str] = Field(default=None, description="Selected retrieval strategy")
    
    # Retrieval results
    bm25_results: List[Any] = Field(default_factory=list, description="Raw BM25 retrieval results")
    milvus_results: List[Any] = Field(default_factory=list, description="Raw Milvus retrieval results")
    combined_results: List[Any] = Field(default_factory=list, description="Merged retrieval results (deduped)")
    candidate_chunk_ids: List[str] = Field(default_factory=list, description="Initial retrieval candidate IDs")
    reranked_chunk_ids: List[str] = Field(default_factory=list, description="Reranked chunk IDs")
    reranked_results: List[Any] = Field(default_factory=list, description="Reranked results objects")
    topk_results: List[Any] = Field(default_factory=list, description="Top-K results after selection")
    parent_doc_keys: List[str] = Field(default_factory=list, description="Parent document R2 keys")
    context_bundle_key: Optional[str] = Field(default=None, description="R2 key for assembled context")
    synthesis_prompt_key: Optional[str] = Field(default=None, description="R2 key for synthesis prompt")
    
    # Extended retrieval context (for LangChain integration)
    retrieval_results: List[Any] = Field(default_factory=list, description="Full retrieval results from LangChain engine")
    bundled_context: List[Dict[str, Any]] = Field(default_factory=list, description="Bundled parent document context")
    context_tokens: int = Field(default=0, description="Total tokens in bundled context")
    authoritative_sources: List[str] = Field(default_factory=list, description="List of authoritative source citations")
    
    # Final outputs
    synthesis: Optional[Dict[str, Any]] = Field(default=None, description="Structured synthesis object")
    final_answer: Optional[str] = Field(default=None, description="Generated answer")
    cited_sources: List[Citation] = Field(default_factory=list, description="Source citations")
    safety_flags: Dict[str, bool] = Field(default_factory=dict, description="Safety and quality flags")
    
    # Performance metadata
    node_timings: Dict[str, float] = Field(default_factory=dict, description="Per-node execution times (ms)")
    total_tokens_used: Optional[int] = Field(default=None, description="Total LLM tokens consumed")
    costs: Dict[str, float] = Field(default_factory=dict, description="Per-node or model cost in USD")
    errors: List[str] = Field(default_factory=list, description="Non-fatal errors encountered during processing")
    
    # Internal adaptive parameters
    retrieval_top_k: Optional[int] = Field(default=None, description="Adaptive retrieval top_k parameter")
    rerank_top_k: Optional[int] = Field(default=None, description="Adaptive rerank top_k parameter")
    
    # Speculative prefetch cache (internal use)
    parent_doc_cache: Dict[str, Any] = Field(default_factory=dict, description="Speculatively prefetched parent documents")
    prefetch_count: Optional[int] = Field(default=None, description="Number of documents prefetched")
    
    # Memory context
    short_term_context: List[Dict[str, Any]] = Field(default_factory=list, description="Conversation history (last N messages)")
    long_term_profile: Dict[str, Any] = Field(default_factory=dict, description="User profile and preferences")
    memory_tokens_used: int = Field(default=0, description="Tokens used by memory context")
    conversation_topics: List[str] = Field(default_factory=list, description="Topics from conversation")
    
    # Self-correction and refinement (ARCH-049, ARCH-050, ARCH-051)
    refinement_iteration: int = Field(default=0, description="Number of refinement iterations performed")
    quality_passed: Optional[bool] = Field(default=None, description="Whether quality gate passed")
    quality_confidence: Optional[float] = Field(default=None, description="Quality confidence score (0.0-1.0)")
    quality_issues: List[str] = Field(default_factory=list, description="Quality issues identified by quality gate")
    refinement_instructions: List[str] = Field(default_factory=list, description="Instructions from self-critic for refinement")
    refinement_strategy: Optional[Literal["pass", "refine_synthesis", "retrieve_more", "fail"]] = Field(
        default=None, description="Decided refinement strategy"
    )
    
    class Config:
        """Pydantic configuration."""
        # Enable JSON serialization of datetime
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        # Validate on assignment
        validate_assignment = True
        # Allow extra fields for extensibility
        extra = "forbid"  # Strict for now, can change to "allow" later
    
    def model_dump_json(self, **kwargs) -> str:
        """Custom JSON serialization with size optimization."""
        # Exclude None values to reduce size
        kwargs.setdefault("exclude_none", True)
        return super().model_dump_json(**kwargs)
    
    def get_size_estimate(self) -> int:
        """Estimate state size in bytes for monitoring."""
        json_str = self.model_dump_json()
        return len(json_str.encode('utf-8'))
    
    def add_timing(self, node_name: str, duration_ms: float) -> None:
        """Add execution timing for a node."""
        self.node_timings[node_name] = duration_ms
    
    def set_safety_flag(self, flag_name: str, value: bool) -> None:
        """Set a safety or quality flag."""
        self.safety_flags[flag_name] = value
    
    def is_oversized(self, max_kb: int = 8) -> bool:
        """Check if state exceeds size limit."""
        return self.get_size_estimate() > (max_kb * 1024)


class StreamEvent(BaseModel):
    """Streaming event emitted during query processing."""
    
    event_type: Literal["meta", "token", "citation", "warning", "final"] = Field(description="Event type")
    trace_id: str = Field(description="Trace identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    payload: Dict[str, Any] = Field(description="Event-specific data")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Utility functions for state management

def create_initial_state(
    user_id: str,
    session_id: str,
    raw_query: str,
    session_history_ids: Optional[List[str]] = None,
    user_profile_key: Optional[str] = None
) -> AgentState:
    """Create initial state for a new query."""
    return AgentState(
        user_id=user_id,
        session_id=session_id,
        raw_query=raw_query,
        session_history_ids=session_history_ids or [],
        user_profile_key=user_profile_key
    )


def validate_state_size(state: AgentState, max_kb: int = 8) -> None:
    """Validate that state doesn't exceed size limits."""
    if state.is_oversized(max_kb):
        size_kb = state.get_size_estimate() / 1024
        raise ValueError(f"AgentState too large: {size_kb:.1f}KB > {max_kb}KB limit")


# State update helpers for LangGraph nodes

def update_intent_routing(state: AgentState, **kwargs) -> Dict[str, Any]:
    """Helper for intent router node updates."""
    return {
        "intent": kwargs.get("intent"),
        "jurisdiction": kwargs.get("jurisdiction"),
        "date_context": kwargs.get("date_context")
    }


def update_query_processing(state: AgentState, **kwargs) -> Dict[str, Any]:
    """Helper for query processing node updates."""
    return {
        "rewritten_query": kwargs.get("rewritten_query"),
        "hypothetical_docs": kwargs.get("hypothetical_docs", []),
        "sub_questions": kwargs.get("sub_questions", [])
    }


def update_retrieval_results(state: AgentState, **kwargs) -> Dict[str, Any]:
    """Helper for retrieval node updates."""
    return {
        "candidate_chunk_ids": kwargs.get("candidate_chunk_ids", []),
        "reranked_chunk_ids": kwargs.get("reranked_chunk_ids", []),
        "parent_doc_keys": kwargs.get("parent_doc_keys", []),
        "context_bundle_key": kwargs.get("context_bundle_key")
    }


def update_final_output(state: AgentState, **kwargs) -> Dict[str, Any]:
    """Helper for synthesis node updates."""
    return {
        "final_answer": kwargs.get("final_answer"),
        "cited_sources": kwargs.get("cited_sources", []),
        "synthesis_prompt_key": kwargs.get("synthesis_prompt_key"),
        "total_tokens_used": kwargs.get("total_tokens_used")
    }
