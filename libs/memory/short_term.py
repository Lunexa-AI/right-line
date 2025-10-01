"""
Short-term memory for conversation context.

Stores recent conversation messages in Redis for:
- Pronoun resolution
- Follow-up question handling  
- Conversation coherence
- Context-aware query rewriting

Follows .cursorrules: async-first, sliding window, token budget management.
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class ShortTermMemory:
    """
    Manages conversation context within a session using Redis.
    
    Features:
    - Sliding window (keeps last N messages)
    - Token budget management
    - 24-hour TTL
    - Exchange grouping (Q&A pairs)
    
    Usage:
        memory = ShortTermMemory(redis_client, max_messages=10)
        await memory.add_message(session_id, "user", "What is labour law?")
        await memory.add_message(session_id, "assistant", "Labour law...")
        context = await memory.get_context(session_id, max_tokens=2000)
    """
    
    def __init__(self, redis_client, max_messages: int = 10):
        """
        Initialize short-term memory.
        
        Args:
            redis_client: Async Redis client
            max_messages: Maximum messages to keep (sliding window)
        """
        self.redis = redis_client
        self.max_messages = max_messages
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add message to session history with sliding window.
        
        Args:
            session_id: Session identifier
            role: "user" or "assistant"
            content: Message content
            metadata: Optional metadata (intent, complexity, etc.)
        """
        key = f"session:{session_id}:messages"
        
        # Create message object
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        # Add to Redis list (LPUSH for newest first)
        await self.redis.lpush(key, json.dumps(message))
        
        # Trim to max_messages (keep only recent)
        await self.redis.ltrim(key, 0, self.max_messages - 1)
        
        # Set TTL (24 hours = 86400 seconds)
        await self.redis.expire(key, 86400)
        
        logger.debug(
            "Message added to short-term memory",
            session_id=session_id,
            role=role,
            content_length=len(content)
        )
    
    async def get_context(
        self,
        session_id: str,
        max_tokens: int = 2000
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversation context within token budget.
        
        Args:
            session_id: Session identifier
            max_tokens: Maximum tokens to return
            
        Returns:
            List of messages (chronological order)
        """
        key = f"session:{session_id}:messages"
        
        # Get all messages (newest first from Redis)
        messages_json = await self.redis.lrange(key, 0, -1)
        
        if not messages_json:
            return []
        
        # Parse and build context
        context = []
        current_tokens = 0
        
        for msg_json in messages_json:
            message = json.loads(msg_json)
            
            # Estimate tokens (rough: 4 chars per token)
            msg_tokens = len(message["content"]) // 4
            
            if current_tokens + msg_tokens > max_tokens:
                break
            
            context.append(message)
            current_tokens += msg_tokens
        
        # Reverse to chronological order (oldest first)
        return list(reversed(context))
    
    async def get_last_n_exchanges(
        self,
        session_id: str,
        n: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get last N query-response exchanges.
        
        Args:
            session_id: Session identifier
            n: Number of exchanges to return
            
        Returns:
            List of exchanges, each with 'user' and 'assistant' messages
        """
        messages = await self.get_context(session_id)
        
        # Group into exchanges
        exchanges = []
        current_exchange = {}
        
        for msg in messages:
            if msg["role"] == "user":
                # Start new exchange
                if current_exchange:
                    exchanges.append(current_exchange)
                current_exchange = {"user": msg}
            elif msg["role"] == "assistant":
                # Complete current exchange
                current_exchange["assistant"] = msg
        
        # Add last exchange if not complete
        if current_exchange:
            exchanges.append(current_exchange)
        
        # Return last N exchanges
        return exchanges[-n:] if len(exchanges) >= n else exchanges
    
    async def clear_session(self, session_id: str):
        """
        Clear session history.
        
        Args:
            session_id: Session identifier
        """
        key = f"session:{session_id}:messages"
        await self.redis.delete(key)
        
        logger.info("Session cleared", session_id=session_id)
