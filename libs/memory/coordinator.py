"""
Memory coordinator for unified memory management.

Combines short-term and long-term memory with:
- Token budget allocation (70% short-term, 30% long-term)
- Parallel fetching for performance
- Unified update interface

Follows .cursorrules: async-first, resource efficiency, clean interfaces.
"""

import asyncio
from typing import Dict, Any
from datetime import datetime

import structlog

logger = structlog.get_logger(__name__)


class MemoryCoordinator:
    """
    Coordinates short-term and long-term memory systems.
    
    Features:
    - Unified interface for memory operations
    - Token budget allocation across memory types
    - Parallel fetching for performance
    - Combined context retrieval
    
    Usage:
        coordinator = MemoryCoordinator(redis_client, firestore_client)
        context = await coordinator.get_full_context(user_id, session_id)
        await coordinator.update_memories(user_id, session_id, query, response, metadata)
    """
    
    def __init__(self, redis_client, firestore_client):
        """
        Initialize memory coordinator.
        
        Args:
            redis_client: Async Redis client for short-term memory
            firestore_client: Async Firestore client for long-term memory
        """
        from libs.memory.short_term import ShortTermMemory
        from libs.memory.long_term import LongTermMemory
        
        self.short_term = ShortTermMemory(redis_client)
        self.long_term = LongTermMemory(firestore_client)
    
    async def get_full_context(
        self,
        user_id: str,
        session_id: str,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Get combined memory context from both systems.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            max_tokens: Total token budget for memory
            
        Returns:
            Dict with conversation_history, user_profile, and tokens_used
        """
        # Allocate token budget
        short_term_budget = int(max_tokens * 0.7)  # 70% to recent conversation
        long_term_budget = int(max_tokens * 0.3)   # 30% to user profile
        
        try:
            # Fetch in parallel for performance
            short_term_task = self.short_term.get_context(session_id, short_term_budget)
            long_term_task = self.long_term.get_personalization_context(user_id)
            
            short_term_context, long_term_context = await asyncio.gather(
                short_term_task,
                long_term_task,
                return_exceptions=True
            )
            
            # Handle errors gracefully
            if isinstance(short_term_context, Exception):
                logger.error("Failed to get short-term context", error=str(short_term_context))
                short_term_context = []
            
            if isinstance(long_term_context, Exception):
                logger.error("Failed to get long-term context", error=str(long_term_context))
                long_term_context = {}
            
            # Calculate actual tokens used
            short_term_tokens = sum(len(m.get("content", "")) // 4 for m in short_term_context)
            long_term_tokens = len(str(long_term_context)) // 4
            
            return {
                "conversation_history": short_term_context,
                "user_profile": long_term_context,
                "tokens_used": {
                    "short_term": short_term_tokens,
                    "long_term": long_term_tokens,
                    "total": short_term_tokens + long_term_tokens
                }
            }
            
        except Exception as e:
            logger.error("Failed to get full context", error=str(e))
            return {
                "conversation_history": [],
                "user_profile": {},
                "tokens_used": {"short_term": 0, "long_term": 0, "total": 0}
            }
    
    async def update_memories(
        self,
        user_id: str,
        session_id: str,
        query: str,
        response: str,
        metadata: Dict[str, Any]
    ):
        """
        Update both memory systems after query.
        
        Args:
            user_id: User identifier
            session_id: Session identifier  
            query: User query
            response: AI response
            metadata: Query metadata (complexity, legal_areas, user_type, etc.)
        """
        try:
            # Update short-term (conversation)
            short_term_task = asyncio.create_task(
                self.short_term.add_message(session_id, "user", query, metadata)
            )
            
            # Add assistant message
            response_task = asyncio.create_task(
                self.short_term.add_message(session_id, "assistant", response)
            )
            
            # Update long-term (patterns)
            long_term_task = asyncio.create_task(
                self.long_term.update_after_query(
                    user_id=user_id,
                    query=query,
                    complexity=metadata.get("complexity", "moderate"),
                    legal_areas=metadata.get("legal_areas", []),
                    user_type=metadata.get("user_type", "citizen")
                )
            )
            
            # Wait for all updates
            await asyncio.gather(
                short_term_task,
                response_task,
                long_term_task,
                return_exceptions=True
            )
            
            logger.debug("Memories updated",
                        user_id=user_id,
                        session_id=session_id)
            
        except Exception as e:
            logger.error("Failed to update memories", error=str(e))
