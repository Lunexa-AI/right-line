"""
Message compression for token efficiency.

Compresses old conversation messages while preserving:
- Key legal terms
- Case citations
- Essential context

Follows .cursorrules: async-first, quality preservation, measurable results.
"""

from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


class MessageCompressor:
    """
    Compresses conversation messages to save tokens.
    
    Features:
    - LLM-based summarization
    - Preserves legal terms and citations
    - 50-70% token reduction target
    - Quality preservation
    
    Usage:
        compressor = MessageCompressor()
        compressed = await compressor.compress_message(long_message)
    """
    
    def __init__(self):
        """Initialize message compressor."""
        self._llm = None
    
    async def compress_message(
        self,
        message: str,
        min_length: int = 100
    ) -> str:
        """
        Compress a message using LLM summarization.
        
        Args:
            message: Message to compress
            min_length: Don't compress if shorter than this
            
        Returns:
            Compressed message
        """
        # Don't compress if already short
        if len(message) < min_length:
            return message
        
        try:
            from langchain_openai import ChatOpenAI
            
            # Initialize LLM if needed
            if self._llm is None:
                self._llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0,
                    max_tokens=150,
                    timeout=5.0
                )
            
            # Compression prompt
            prompt = f"""Compress this legal conversation message while preserving:
- Key legal terms and concepts
- Case citations (e.g., "Smith v Zimbabwe SC 12/2020")
- Statutory references (e.g., "Section 12", "Labour Act Chapter 28:01")
- Essential facts and conclusions

Original message:
{message}

Provide a concise summary (aim for 50% reduction) that preserves all critical legal information.
Return ONLY the compressed version, no explanation."""
            
            response = await self._llm.ainvoke(prompt)
            compressed = response.content.strip()
            
            # Calculate reduction
            original_tokens = len(message) // 4
            compressed_tokens = len(compressed) // 4
            reduction = ((original_tokens - compressed_tokens) / original_tokens) * 100
            
            logger.debug(
                "Message compressed",
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                reduction_pct=round(reduction, 1)
            )
            
            return compressed
            
        except Exception as e:
            logger.warning("Message compression failed, returning original", error=str(e))
            return message
