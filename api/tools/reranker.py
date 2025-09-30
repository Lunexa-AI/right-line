#!/usr/bin/env python3
"""BGE-reranker-v2 implementation for RightLine retrieval system.

This module provides a production-grade reranking capability using the
BGE-reranker-v2 model from BAAI. The reranker improves retrieval quality
by reordering candidate chunks based on their actual relevance to the query.

Usage:
    from api.reranker import BGEReranker
    
    reranker = BGEReranker()
    reranked_results = await reranker.rerank(query, candidate_chunks, top_k=10)
"""

import asyncio
import logging
import time
from typing import List, Optional, Tuple

import structlog

# Optional dependency: sentence-transformers
try:
    from sentence_transformers import CrossEncoder  # type: ignore
except Exception:  # pragma: no cover - optional in some environments (e.g., Studio)
    CrossEncoder = None  # type: ignore

logger = structlog.get_logger(__name__)


class BGEReranker:
    """Production BGE-reranker-v2 for improving retrieval quality."""
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2"):
        """Initialize optimized reranker for <2.5s latency.
        
        Args:
            model_name: HuggingFace model name (using smallest/fastest model)
        """
        self.model_name = model_name
        self.model: Optional[CrossEncoder] = None
        self._loading = False
        self._model_cache = {}  # Cache loaded models
        self._lib_available = CrossEncoder is not None
        
    async def _load_model(self) -> None:
        """Load the reranker model (async to avoid blocking)."""
        if self.model is not None or self._loading:
            return
            
        self._loading = True
        try:
            if not self._lib_available:
                logger.warning(
                    "sentence-transformers not installed; skipping reranker load",
                    model=self.model_name,
                )
                return
            logger.info("Loading BGE reranker model", model=self.model_name)
            start_time = time.time()
            
            # Load model in thread to avoid blocking (optimized for speed)
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, 
                lambda: CrossEncoder(
                    self.model_name, 
                    max_length=256,  # Reduced for speed
                    device='cpu'     # Force CPU for consistent performance
                )
            )
            
            load_time = time.time() - start_time
            logger.info("BGE reranker model loaded successfully", 
                       model=self.model_name, 
                       load_time_ms=round(load_time * 1000, 2))
                       
        except Exception as e:
            logger.error("Failed to load BGE reranker model", 
                        model=self.model_name, 
                        error=str(e))
            raise
        finally:
            self._loading = False
    
    async def rerank(
        self, 
        query: str, 
        candidates: List, 
        top_k: Optional[int] = None
    ) -> List:
        """Rerank candidate results using BGE-reranker-v2.
        
        Args:
            query: The search query
            candidates: List of candidate RetrievalResult objects
            top_k: Number of top results to return (None = return all)
            
        Returns:
            Reranked list of RetrievalResult objects with updated scores
        """
        if not candidates:
            return []
            
        # Ensure model is loaded
        await self._load_model()
        
        if self.model is None:
            logger.warning("BGE reranker model not available, returning original order")
            return candidates[:top_k] if top_k else candidates
        
        start_time = time.time()
        
        try:
            # Prepare query-document pairs for reranking
            query_doc_pairs = []
            for candidate in candidates:
                # Use chunk text if available, otherwise use a preview
                doc_text = candidate.chunk_text
                if not doc_text:
                    # Fallback to metadata or empty string
                    doc_text = candidate.metadata.get("section_path", "")
                
                # Truncate for speed (shorter = faster inference)
                if len(doc_text) > 500:
                    doc_text = doc_text[:500] + "..."
                    
                query_doc_pairs.append([query, doc_text])
            
            logger.info("Starting BGE reranking", 
                       query_preview=query[:50],
                       candidates=len(candidates))
            
            # Run reranking in thread to avoid blocking
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(
                None,
                lambda: self.model.predict(query_doc_pairs)
            )
            
            # Create reranked results with new scores
            reranked_candidates = []
            for i, (candidate, new_score) in enumerate(zip(candidates, scores)):
                # Update confidence (score is read-only property that returns confidence)
                candidate.confidence = float(new_score)
                candidate.metadata.update({
                    "original_confidence": candidate.confidence,
                    "reranker_score": float(new_score),
                    "reranker_model": self.model_name,
                    "source": f"{candidate.metadata.get('source', 'unknown')}_reranked"
                })
                reranked_candidates.append(candidate)
            
            # Sort by new scores (descending)
            reranked_candidates.sort(key=lambda x: x.score, reverse=True)
            
            # Apply top_k limit if specified
            final_results = reranked_candidates[:top_k] if top_k else reranked_candidates
            
            rerank_time = time.time() - start_time
            
            logger.info("BGE reranking completed",
                       input_candidates=len(candidates),
                       output_results=len(final_results),
                       rerank_time_ms=round(rerank_time * 1000, 2),
                       top_score=final_results[0].score if final_results else 0,
                       score_improvement=round(final_results[0].score - candidates[0].score, 4) if final_results and candidates else 0)
            
            return final_results
            
        except Exception as e:
            logger.error("BGE reranking failed, returning original order",
                        error=str(e),
                        candidates=len(candidates))
            return candidates[:top_k] if top_k else candidates


class RerankerConfig:
    """Configuration for reranking behavior."""
    
    def __init__(
        self,
        enabled: bool = True,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        min_candidates: int = 3,
        max_candidates: int = 50,
        top_k_after_rerank: Optional[int] = None
    ):
        self.enabled = enabled
        self.model_name = model_name
        self.min_candidates = min_candidates
        self.max_candidates = max_candidates
        self.top_k_after_rerank = top_k_after_rerank


# Global reranker instance (pre-loaded for performance)
_global_reranker: Optional[BGEReranker] = None
_reranker_loading = False


async def get_reranker() -> BGEReranker:
    """Get or create the global reranker instance with pre-loading."""
    global _global_reranker, _reranker_loading
    
    if _global_reranker is None and not _reranker_loading:
        _reranker_loading = True
        try:
            _global_reranker = BGEReranker()
            # Pre-load the model immediately
            await _global_reranker._load_model()
        finally:
            _reranker_loading = False
            
    return _global_reranker


async def warmup_reranker() -> None:
    """Warmup reranker during application startup."""
    logger.info("Warming up reranker for optimal performance")
    try:
        reranker = await get_reranker()
        logger.info("Reranker warmed up successfully")
    except Exception as e:
        logger.warning("Reranker warmup failed", error=str(e))
