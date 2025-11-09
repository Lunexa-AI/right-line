"""
GPT-5 Pro wrapper for the Responses API.

This module provides a LangChain-compatible wrapper for GPT-5 models
that use OpenAI's new Responses API instead of Chat Completions.
"""

import os
import asyncio
from typing import Any, Dict, List, Optional, AsyncIterator
from dataclasses import dataclass

import structlog
from openai import AsyncOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, AIMessageChunk
from langchain_core.outputs import Generation, LLMResult, ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class GPT5ProWrapper(BaseChatModel):
    """
    Wrapper for GPT-5 Pro using the Responses API.
    
    This wrapper allows GPT-5 Pro to be used with LangChain workflows
    despite the API differences.
    """
    
    model: str = Field(default="gpt-5-pro")
    temperature: float = Field(default=0.1)
    max_tokens: int = Field(default=2000)
    reasoning_effort: str = Field(default="high")  # GPT-5 Pro only supports "high"
    verbosity: str = Field(default="medium")
    client: Optional[AsyncOpenAI] = Field(default=None, exclude=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.client:
            self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    @property
    def _llm_type(self) -> str:
        return "gpt5-pro"
    
    def _convert_messages_to_input(self, messages: List[BaseMessage]) -> str:
        """Convert LangChain messages to Responses API input format."""
        # For GPT-5 Pro, we can pass messages as a formatted string
        formatted_messages = []
        
        for msg in messages:
            if isinstance(msg, SystemMessage):
                formatted_messages.append(f"System: {msg.content}")
            elif isinstance(msg, HumanMessage):
                formatted_messages.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted_messages.append(f"Assistant: {msg.content}")
            else:
                formatted_messages.append(msg.content)
        
        return "\n\n".join(formatted_messages)
    
    def _extract_output_text(self, response: Any) -> str:
        """Extract plain text from Responses API output (robust to SDK/dict).
        Falls back to string conversion if structured fields are missing.
        """
        # Prefer helper if present
        text_val = getattr(response, "output_text", None)
        if isinstance(text_val, str) and text_val.strip():
            return text_val
        
        # Convert to plain dict if possible
        data = None
        try:
            if hasattr(response, "model_dump"):
                data = response.model_dump()
            elif hasattr(response, "to_dict"):
                data = response.to_dict()  # type: ignore[attr-defined]
        except Exception:
            data = None
        if data is None:
            data = response
        
        def get(obj: Any, key: str) -> Any:
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)
        
        # Responses API: data["output"] is a list of items; message items have content array
        output = get(data, "output")
        parts: List[str] = []
        if isinstance(output, (list, tuple)):
            for item in output:
                item_type = get(item, "type")
                if item_type == "message":
                    content_list = get(item, "content")
                    if isinstance(content_list, (list, tuple)):
                        for content_item in content_list:
                            # Different SDKs may use different shapes
                            text_piece = (
                                get(content_item, "text")
                                or get(content_item, "value")
                                or get(content_item, "data")
                            )
                            if isinstance(text_piece, str):
                                parts.append(text_piece)
        if parts:
            return "".join(parts)
        
        # Last resort
        try:
            return str(text_val or "").strip()
        except Exception:
            return ""
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate response using GPT-5 Pro via Responses API."""
        try:
            input_text = self._convert_messages_to_input(messages)
            
            # Use the Responses API
            response = await self.client.responses.create(
                model=self.model,
                input=input_text,
                reasoning={"effort": self.reasoning_effort},
                text={
                    "verbosity": self.verbosity
                },
                max_output_tokens=self.max_tokens,
                store=False  # For privacy, don't store responses
            )
            
            # Extract the output text robustly
            output_text = self._extract_output_text(response)
            
            message = AIMessage(content=output_text)
            generation = ChatGeneration(message=message)
            return ChatResult(generations=[generation])
            
        except Exception as e:
            logger.error("GPT-5 Pro generation failed", error=str(e))
            raise
    
    async def astream(
        self,
        input: Any,
        config: Optional[Any] = None,
        **kwargs: Any
    ) -> AsyncIterator[AIMessageChunk]:
        """Stream responses from GPT-5 Pro."""
        try:
            # Convert input to appropriate format
            if isinstance(input, list):
                input_text = self._convert_messages_to_input(input)
            else:
                input_text = str(input)
            
            # GPT-5 Pro doesn't support streaming in the same way
            # We'll simulate streaming by yielding the full response
            response = await self.client.responses.create(
                model=self.model,
                input=input_text,
                reasoning={"effort": self.reasoning_effort},
                text={
                    "verbosity": self.verbosity
                },
                max_output_tokens=self.max_tokens,
                store=False
            )
            
            # Extract output text robustly
            output_text = self._extract_output_text(response)
            
            # Simulate streaming by yielding AIMessageChunk pieces
            chunk_size = 200
            for i in range(0, len(output_text), chunk_size):
                yield AIMessageChunk(content=output_text[i:i+chunk_size])
                await asyncio.sleep(0.005)
                
        except Exception as e:
            logger.error("GPT-5 Pro streaming failed", error=str(e))
            raise
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Synchronous generation (runs async version)."""
        return asyncio.run(self._agenerate(messages, stop, run_manager, **kwargs))
    
    async def ainvoke(self, input: Any, config: Optional[Any] = None, **kwargs) -> Any:
        """Async invoke for chat model compatibility."""
        messages = input if isinstance(input, list) else [HumanMessage(content=str(input))]
        result = await self._agenerate(messages, **kwargs)
        return result.generations[0].message
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get identifying parameters."""
        return {
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "verbosity": self.verbosity
        }


class GPT5Wrapper(BaseChatModel):
    """
    Wrapper for standard GPT-5 (not Pro) using the Responses API.
    Supports multiple reasoning efforts.
    """
    
    model: str = Field(default="gpt-5")
    temperature: float = Field(default=0.1)
    max_tokens: int = Field(default=1500)
    reasoning_effort: str = Field(default="medium")  # low, medium, high
    verbosity: str = Field(default="medium")
    client: Optional[AsyncOpenAI] = Field(default=None, exclude=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.client:
            self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    @property
    def _llm_type(self) -> str:
        return "gpt5"
    
    def _convert_messages_to_input(self, messages: List[BaseMessage]) -> str:
        """Convert LangChain messages to Responses API input format."""
        formatted_messages = []
        
        for msg in messages:
            if isinstance(msg, SystemMessage):
                formatted_messages.append(f"System: {msg.content}")
            elif isinstance(msg, HumanMessage):
                formatted_messages.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted_messages.append(f"Assistant: {msg.content}")
            else:
                formatted_messages.append(msg.content)
        
        return "\n\n".join(formatted_messages)
    
    def _extract_output_text(self, response: Any) -> str:
        """Extract plain text from Responses API output (robust to SDK/dict).
        Falls back to string conversion if structured fields are missing.
        """
        # Prefer helper if present
        text_val = getattr(response, "output_text", None)
        if isinstance(text_val, str) and text_val.strip():
            return text_val
        
        # Convert to plain dict if possible
        data = None
        try:
            if hasattr(response, "model_dump"):
                data = response.model_dump()
            elif hasattr(response, "to_dict"):
                data = response.to_dict()  # type: ignore[attr-defined]
        except Exception:
            data = None
        if data is None:
            data = response
        
        def get(obj: Any, key: str) -> Any:
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)
        
        # Responses API: data["output"] is a list of items; message items have content array
        output = get(data, "output")
        parts: List[str] = []
        if isinstance(output, (list, tuple)):
            for item in output:
                item_type = get(item, "type")
                if item_type == "message":
                    content_list = get(item, "content")
                    if isinstance(content_list, (list, tuple)):
                        for content_item in content_list:
                            # Different SDKs may use different shapes
                            text_piece = (
                                get(content_item, "text")
                                or get(content_item, "value")
                                or get(content_item, "data")
                            )
                            if isinstance(text_piece, str):
                                parts.append(text_piece)
        if parts:
            return "".join(parts)
        
        # Last resort
        try:
            return str(text_val or "").strip()
        except Exception:
            return ""
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate response using GPT-5 via Responses API."""
        try:
            input_text = self._convert_messages_to_input(messages)
            
            response = await self.client.responses.create(
                model=self.model,
                input=input_text,
                reasoning={"effort": self.reasoning_effort},
                text={
                    "verbosity": self.verbosity
                },
                max_output_tokens=self.max_tokens,
                store=False
            )
            
            output_text = self._extract_output_text(response)
            
            message = AIMessage(content=output_text)
            generation = ChatGeneration(message=message)
            return ChatResult(generations=[generation])
            
        except Exception as e:
            logger.error("GPT-5 generation failed", error=str(e))
            raise
    
    async def astream(
        self,
        input: Any,
        config: Optional[Any] = None,
        **kwargs: Any
    ) -> AsyncIterator[AIMessageChunk]:
        """Stream responses from GPT-5."""
        try:
            if isinstance(input, list):
                input_text = self._convert_messages_to_input(input)
            else:
                input_text = str(input)
            
            response = await self.client.responses.create(
                model=self.model,
                input=input_text,
                reasoning={"effort": self.reasoning_effort},
                text={
                    "verbosity": self.verbosity
                },
                max_output_tokens=self.max_tokens,
                store=False
            )
            
            output_text = self._extract_output_text(response)
            
            # Simulate streaming by yielding AIMessageChunk pieces
            chunk_size = 50
            for i in range(0, len(output_text), chunk_size):
                yield AIMessageChunk(content=output_text[i:i+chunk_size])
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error("GPT-5 streaming failed", error=str(e))
            raise
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Synchronous generation."""
        return asyncio.run(self._agenerate(messages, stop, run_manager, **kwargs))
    
    async def ainvoke(self, input: Any, config: Optional[Any] = None, **kwargs) -> Any:
        """Async invoke for chat model compatibility."""
        messages = input if isinstance(input, list) else [HumanMessage(content=str(input))]
        result = await self._agenerate(messages, **kwargs)
        return result.generations[0].message
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get identifying parameters."""
        return {
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "verbosity": self.verbosity
        }


def get_gpt5_model(
    model_name: str = "gpt-5-pro",
    reasoning_effort: str = "high",
    max_tokens: int = 2000,
    verbosity: str = "medium"
) -> BaseChatModel:
    """
    Factory function to get appropriate GPT-5 model wrapper.
    
    Args:
        model_name: "gpt-5-pro", "gpt-5", "gpt-5-mini", "gpt-5-nano"
        reasoning_effort: "low", "medium", "high" (Pro only supports "high")
        max_tokens: Maximum output tokens
        verbosity: "low", "medium", "high"
    
    Returns:
        Appropriate GPT-5 wrapper for LangChain
    """
    if model_name == "gpt-5-pro":
        return GPT5ProWrapper(
            model=model_name,
            max_tokens=max_tokens,
            reasoning_effort="high",  # Pro only supports high
            verbosity=verbosity
        )
    else:
        return GPT5Wrapper(
            model=model_name,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity
        )
