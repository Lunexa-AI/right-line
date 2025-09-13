"""OpenAI-based answer composition for Gweta.

This module implements two-stage answer composition:
1. Extractive fallback - Fast, deterministic summary from retrieved chunks
2. OpenAI enhancement - GPT-powered rewriting for better user experience

Follows .cursorrules principles: fallback-first, cost monitoring, prompt safety.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from api.retrieval import RetrievalResult
from api.models import ParentDocumentV3 as ParentDocument

logger = structlog.get_logger(__name__)

# OpenAI configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
OPENAI_MAX_TOKENS = int(os.environ.get("OPENAI_MAX_TOKENS", "300"))

# Cost tracking
OPENAI_COSTS = {
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},  # per 1K tokens
    "gpt-5-mini": {"input": 0.00015, "output": 0.0006},
}


class ComposedAnswer(BaseModel):
    """Structured answer format following .cursorrules schema."""
    
    tldr: str = Field(max_length=220, description="Brief summary")
    key_points: List[str] = Field(max_items=5, description="3-5 key points, ≤25 words each")
    citations: List[Dict[str, Any]] = Field(description="Source references")
    suggestions: List[str] = Field(max_items=3, description="2-3 follow-up questions")
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = Field(description="extractive, openai, or hybrid")


class OpenAIResponse(BaseModel):
    """Expected JSON structure from OpenAI."""
    
    tldr: str = Field(max_length=220)
    key_points: List[str] = Field(max_items=5)
    suggestions: List[str] = Field(max_items=3)


@dataclass
class TokenUsage:
    """Track token usage for cost monitoring."""
    
    input_tokens: int
    output_tokens: int
    model: str
    cost_usd: float


class ExtractiveComposer:
    """Fast, deterministic composition from retrieved chunks."""
    
    @staticmethod
    def extract_key_sentences(text: str, max_sentences: int = 3) -> List[str]:
        """Extract key sentences from text."""
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        # Score sentences by length and legal keywords
        legal_keywords = {
            'shall', 'must', 'may', 'entitled', 'liable', 'penalty', 'fine',
            'imprisonment', 'court', 'tribunal', 'employer', 'employee'
        }
        
        scored_sentences = []
        for sentence in sentences:
            score = 0
            words = sentence.lower().split()
            
            # Length score (prefer medium-length sentences)
            if 5 <= len(words) <= 25:
                score += 2
            elif len(words) > 25:
                score += 1
            
            # Legal keyword score
            for word in words:
                if word in legal_keywords:
                    score += 1
            
            scored_sentences.append((sentence, score))
        
        # Sort by score and take top sentences
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored_sentences[:max_sentences]]
    
    @staticmethod
    def generate_suggestions(results: List[RetrievalResult], original_query: str) -> List[str]:
        """Generate follow-up suggestions based on retrieved content."""
        suggestions = []
        
        # Extract topics from metadata
        topics = set()
        for result in results:
            metadata = result.metadata
            if isinstance(metadata, dict):
                # Extract section or topic information
                section = metadata.get('section_path', '') # Use section_path for V3
                title = metadata.get('title', '')
                if section:
                    topics.add(section)
                if title and 'act' not in title.lower():
                    topics.add(title)
        
        # Generate contextual suggestions
        query_lower = original_query.lower()
        
        if 'penalty' in query_lower or 'fine' in query_lower:
            suggestions.append("What are the procedures for appealing penalties?")
        elif 'termination' in query_lower or 'dismissal' in query_lower:
            suggestions.append("What notice period is required for termination?")
        elif 'wage' in query_lower or 'salary' in query_lower:
            suggestions.append("How are overtime payments calculated?")
        elif 'leave' in query_lower:
            suggestions.append("What types of leave are available to employees?")
        
        # Add topic-based suggestions
        for topic in list(topics)[:2]:
            if len(suggestions) < 3:
                suggestions.append(f"Tell me more about {topic}")
        
        # Fallback suggestions
        while len(suggestions) < 2:
            fallbacks = [
                "What are the key employment rights in Zimbabwe?",
                "How do I file a complaint with labour authorities?",
                "What are the penalties for labour law violations?"
            ]
            for fallback in fallbacks:
                if fallback not in suggestions and len(suggestions) < 3:
                    suggestions.append(fallback)
                    break
            break
        
        return suggestions[:3]
    
    def compose_extractive(
        self, 
        results: List[RetrievalResult], 
        query: str,
        confidence: float
    ) -> ComposedAnswer:
        """Create extractive answer from retrieval results."""
        if not results:
            return ComposedAnswer(
                tldr="No relevant information found for your query.",
                key_points=["Please try rephrasing your question or contact legal counsel."],
                citations=[],
                suggestions=self.generate_suggestions([], query),
                confidence=0.0,
                source="extractive"
            )
        
        # Combine text from top results
        combined_text = ""
        citations = []
        
        for i, result in enumerate(results[:3]):  # Use top 3 results
            combined_text += f" {result.chunk_text}"
            
            # Build citation using V3 fields
            metadata = result.metadata
            citations.append({
                "id": i + 1,
                "title": metadata.get("title") or f"Document {result.doc_id}",
                "section_path": metadata.get("section_path"),
                "tree_node_id": metadata.get("tree_node_id"),
                "source_url": metadata.get("source_document_key"),
                "score": round(result.score, 3)
            })
        
        # Extract key sentences for TL;DR
        key_sentences = self.extract_key_sentences(combined_text, max_sentences=2)
        tldr = ". ".join(key_sentences)
        if len(tldr) > 220:
            tldr = tldr[:217] + "..."
        
        # Extract key points (more sentences)
        all_sentences = self.extract_key_sentences(combined_text, max_sentences=5)
        key_points = []
        for sentence in all_sentences:
            # Truncate to 25 words
            words = sentence.split()
            if len(words) > 25:
                sentence = " ".join(words[:25]) + "..."
            key_points.append(sentence)
        
        # Generate suggestions
        suggestions = self.generate_suggestions(results, query)
        
        return ComposedAnswer(
            tldr=tldr or "Legal information found - see key points below.",
            key_points=key_points[:5],
            citations=citations,
            suggestions=suggestions,
            confidence=confidence,
            source="extractive"
        )


class OpenAIComposer:
    """OpenAI-powered answer enhancement."""
    
    def __init__(self):
        self.token_usage: List[TokenUsage] = []
    
    def _build_prompt(self, extractive_answer: ComposedAnswer, query: str, lang: str = "en") -> Dict[str, Any]:
        """Build OpenAI prompt following .cursorrules safety guidelines."""
        
        # Sanitize inputs - remove any potential prompt injection
        clean_query = re.sub(r'[^\w\s\-\.\?\!]', ' ', query)[:500]
        clean_tldr = re.sub(r'[^\w\s\-\.\?\!\,]', ' ', extractive_answer.tldr)[:500]
        
        system_prompt = f"""You are a legal information assistant for Zimbabwe law. 
Create a structured summary from the provided legal text.
Return valid JSON with: tldr (≤220 chars), key_points (3-5 bullets, ≤25 words each), suggestions (2-3 follow-ups).
Language: {lang}. If unsure, use extractive text only.
DO NOT invent citations or legal advice. Only restructure the provided information."""
        
        user_prompt = f"""Original query: {clean_query}

Extractive summary: {clean_tldr}

Key points from legal text:
{chr(10).join(f"- {point[:100]}" for point in extractive_answer.key_points[:3])}

Please rewrite this into a more conversational and helpful format while preserving all legal accuracy. 
Return only valid JSON with the required fields."""
        
        return {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_completion_tokens": OPENAI_MAX_TOKENS,
            "temperature": 1.0,
            "response_format": {"type": "json_object"}
        }
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 0.75 words)."""
        return int(len(text.split()) / 0.75)
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Calculate cost based on token usage."""
        costs = OPENAI_COSTS.get(model, OPENAI_COSTS["gpt-3.5-turbo"])
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        return input_cost + output_cost
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def enhance_answer(
        self,
        extractive_answer: ComposedAnswer,
        query: str,
        lang: str = "en",
        timeout: float = 10.0
    ) -> Optional[ComposedAnswer]:
        """Enhance extractive answer using OpenAI."""
        if not OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured")
            return None
        
        start_time = time.time()
        
        try:
            # Build prompt
            prompt_data = self._build_prompt(extractive_answer, query, lang)
            
            # Estimate input tokens
            prompt_text = json.dumps(prompt_data["messages"], indent=2)
            estimated_input_tokens = self._estimate_tokens(prompt_text)
            
            # Check cost limits (simple circuit breaker)
            estimated_cost = self._calculate_cost(estimated_input_tokens, OPENAI_MAX_TOKENS, OPENAI_MODEL)
            if estimated_cost > 0.10:  # $0.10 limit per request
                logger.warning("OpenAI request too expensive", estimated_cost=estimated_cost)
                return None
            
            # Make API call
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=prompt_data
                )
                
                if response.status_code != 200:
                    logger.error(
                        "OpenAI API error",
                        status=response.status_code,
                        response=response.text[:200]
                    )
                    return None
                
                data = response.json()
                
                # Extract usage information
                usage = data.get("usage", {})
                actual_input_tokens = usage.get("prompt_tokens", estimated_input_tokens)
                actual_output_tokens = usage.get("completion_tokens", 0)
                actual_cost = self._calculate_cost(actual_input_tokens, actual_output_tokens, OPENAI_MODEL)
                
                # Track token usage
                self.token_usage.append(TokenUsage(
                    input_tokens=actual_input_tokens,
                    output_tokens=actual_output_tokens,
                    model=OPENAI_MODEL,
                    cost_usd=actual_cost
                ))
                
                # Parse response
                content = data["choices"][0]["message"]["content"]
                openai_response = json.loads(content)
                
                # Validate response structure
                validated_response = OpenAIResponse(**openai_response)
                
                # Create enhanced answer
                enhanced_answer = ComposedAnswer(
                    tldr=validated_response.tldr,
                    key_points=validated_response.key_points,
                    citations=extractive_answer.citations,  # Keep original citations
                    suggestions=validated_response.suggestions,
                    confidence=extractive_answer.confidence,
                    source="openai"
                )
                
                elapsed_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "OpenAI enhancement completed",
                    elapsed_ms=elapsed_ms,
                    input_tokens=actual_input_tokens,
                    output_tokens=actual_output_tokens,
                    cost_usd=round(actual_cost, 6)
                )
                
                return enhanced_answer
                
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error("OpenAI response validation failed", error=str(e))
            return None
        except Exception as e:
            logger.error("OpenAI enhancement failed", error=str(e))
            return None
    
    def get_total_cost(self) -> float:
        """Get total cost of OpenAI usage in current session."""
        return sum(usage.cost_usd for usage in self.token_usage)


class AnswerComposer:
    """Main composer orchestrating extractive and OpenAI composition."""
    
    def __init__(self):
        self.extractive_composer = ExtractiveComposer()
        self.openai_composer = OpenAIComposer()
    
    async def compose_answer(
        self,
        results: List[RetrievalResult],
        query: str,
        confidence: float,
        lang: str = "en",
        use_openai: bool = True
    ) -> ComposedAnswer:
        """
        Compose final answer using two-stage approach.
        
        Args:
            results: Retrieved document chunks
            query: Original user query
            confidence: Retrieval confidence score
            lang: Language hint (en, sn, nd)
            use_openai: Whether to use OpenAI enhancement
        
        Returns:
            Composed answer with appropriate source attribution
        """
        start_time = time.time()
        
        # Stage 1: Always create extractive answer (fast fallback)
        extractive_answer = self.extractive_composer.compose_extractive(results, query, confidence)
        
        logger.info(
            "Extractive composition completed",
            confidence=confidence,
            key_points_count=len(extractive_answer.key_points),
            tldr_length=len(extractive_answer.tldr)
        )
        
        # Stage 2: OpenAI enhancement (if enabled and conditions met)
        if use_openai and confidence > 0.3 and OPENAI_API_KEY:
            enhanced_answer = await self.openai_composer.enhance_answer(
                extractive_answer, query, lang, timeout=8.0
            )
            
            if enhanced_answer:
                # Mark as hybrid since we used both approaches
                enhanced_answer.source = "hybrid"
                final_answer = enhanced_answer
                logger.info("Using OpenAI-enhanced answer")
            else:
                final_answer = extractive_answer
                logger.info("Using extractive fallback (OpenAI failed)")
        else:
            final_answer = extractive_answer
            logger.info("Using extractive answer (OpenAI disabled or low confidence)")
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Answer composition completed",
            elapsed_ms=elapsed_ms,
            source=final_answer.source,
            openai_cost=self.openai_composer.get_total_cost()
        )
        
        return final_answer


# Convenience function for direct use

async def compose_legal_answer(
    results: List[RetrievalResult],
    query: str,
    confidence: float,
    lang: str = "en",
    use_openai: bool = True
) -> ComposedAnswer:
    """
    Compose a legal answer from retrieval results.
    
    Args:
        results: Retrieved document chunks
        query: Original user query  
        confidence: Retrieval confidence score
        lang: Language hint
        use_openai: Whether to use OpenAI enhancement
    
    Returns:
        Composed answer ready for API response
    """
    composer = AnswerComposer()
    return await composer.compose_answer(results, query, confidence, lang, use_openai)
