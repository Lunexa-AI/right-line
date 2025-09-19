"""
Observability and tracing utilities for RightLine Legal Assistant.

This module provides comprehensive tracing, metrics, and observability
for the agentic workflow using LangSmith and OpenTelemetry.

Task 5.1: Observability & Quality Gates Implementation
"""

import asyncio
import functools
import os
import time
from typing import Any, Callable, Dict, Optional

import structlog
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.messages import BaseMessage

# OpenTelemetry imports (optional - install if needed)
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

logger = structlog.get_logger(__name__)


class LangSmithCallbackHandler(BaseCallbackHandler):
    """
    Custom callback handler for enhanced LangSmith tracing.
    
    This handler adds custom metadata and performance metrics
    to LangSmith traces for better observability.
    """
    
    def __init__(self, session_name: str = "rightline-legal-assistant"):
        super().__init__()
        self.session_name = session_name
        self.start_times: Dict[str, float] = {}
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts running."""
        run_id = kwargs.get("run_id")
        if run_id:
            self.start_times[str(run_id)] = time.time()
        
        logger.info(
            "LLM call started",
            model=serialized.get("name", "unknown"),
            prompt_length=sum(len(p) for p in prompts),
            run_id=str(run_id) if run_id else None
        )
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM ends running."""
        run_id = kwargs.get("run_id")
        if run_id and str(run_id) in self.start_times:
            duration = time.time() - self.start_times[str(run_id)]
            del self.start_times[str(run_id)]
            
            # Extract token usage if available
            token_usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}
            
            logger.info(
                "LLM call completed",
                duration_ms=int(duration * 1000),
                generations_count=len(response.generations),
                total_tokens=token_usage.get("total_tokens", 0),
                prompt_tokens=token_usage.get("prompt_tokens", 0),
                completion_tokens=token_usage.get("completion_tokens", 0),
                run_id=str(run_id) if run_id else None
            )
    
    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Called when LLM encounters an error."""
        run_id = kwargs.get("run_id")
        if run_id and str(run_id) in self.start_times:
            duration = time.time() - self.start_times[str(run_id)]
            del self.start_times[str(run_id)]
            
            logger.error(
                "LLM call failed",
                error=str(error),
                duration_ms=int(duration * 1000),
                run_id=str(run_id) if run_id else None
            )


def setup_langsmith_tracing():
    """
    Set up LangSmith tracing with proper configuration.
    
    This function configures LangSmith for both development
    (LangGraph Studio) and production environments.
    """
    
    # Check if LangSmith is enabled
    if not os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true":
        logger.info("LangSmith tracing disabled")
        return
    
    # Validate required environment variables
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        logger.warning("LANGCHAIN_API_KEY not set - LangSmith tracing will not work")
        return
    
    project = os.getenv("LANGCHAIN_PROJECT", "rightline-legal-assistant")
    endpoint = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    
    logger.info(
        "LangSmith tracing enabled",
        project=project,
        endpoint=endpoint
    )
    
    # Set environment variables for LangChain
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = project
    os.environ["LANGCHAIN_ENDPOINT"] = endpoint
    
    return LangSmithCallbackHandler(session_name=project)


def setup_opentelemetry():
    """
    Set up OpenTelemetry tracing for production observability.
    
    This provides additional observability beyond LangSmith,
    including custom application metrics and traces.
    """
    
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available - install opentelemetry packages")
        return
    
    # Check if OpenTelemetry is configured
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not otel_endpoint:
        logger.info("OpenTelemetry not configured")
        return
    
    # Set up tracer provider
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)
    
    # Set up OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=otel_endpoint,
        headers=_parse_otel_headers()
    )
    
    # Add span processor
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    
    # Instrument requests
    RequestsInstrumentor().instrument()
    
    logger.info(
        "OpenTelemetry tracing enabled",
        endpoint=otel_endpoint,
        service_name=os.getenv("OTEL_SERVICE_NAME", "rightline-api")
    )
    
    return tracer


def _parse_otel_headers() -> Dict[str, str]:
    """Parse OpenTelemetry headers from environment."""
    headers_str = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    headers = {}
    
    for header in headers_str.split(","):
        if "=" in header:
            key, value = header.split("=", 1)
            headers[key.strip()] = value.strip()
    
    return headers


def trace_function(operation_name: str):
    """
    Decorator to trace function execution with OpenTelemetry.
    
    Usage:
        @trace_function("retrieve_documents")
        async def retrieve_documents(query: str):
            # Function implementation
            pass
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not OTEL_AVAILABLE:
                return await func(*args, **kwargs)
            
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(operation_name) as span:
                # Add function metadata
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("function.success", True)
                    return result
                except Exception as e:
                    span.set_attribute("function.success", False)
                    span.set_attribute("function.error", str(e))
                    raise
                finally:
                    duration = time.time() - start_time
                    span.set_attribute("function.duration_ms", int(duration * 1000))
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not OTEL_AVAILABLE:
                return func(*args, **kwargs)
            
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(operation_name) as span:
                # Add function metadata
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("function.success", True)
                    return result
                except Exception as e:
                    span.set_attribute("function.success", False)
                    span.set_attribute("function.error", str(e))
                    raise
                finally:
                    duration = time.time() - start_time
                    span.set_attribute("function.duration_ms", int(duration * 1000))
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class PerformanceMonitor:
    """
    Performance monitoring utility for tracking system metrics.
    
    This class provides methods to track and report on system
    performance metrics for optimization purposes.
    """
    
    def __init__(self):
        self.metrics: Dict[str, list] = {
            "retrieval_latency": [],
            "synthesis_latency": [],
            "total_latency": [],
            "confidence_scores": [],
            "result_counts": []
        }
    
    def record_retrieval(self, latency_ms: int, result_count: int, confidence: float):
        """Record retrieval performance metrics."""
        self.metrics["retrieval_latency"].append(latency_ms)
        self.metrics["result_counts"].append(result_count)
        self.metrics["confidence_scores"].append(confidence)
        
        logger.info(
            "Retrieval performance recorded",
            latency_ms=latency_ms,
            result_count=result_count,
            confidence=confidence
        )
    
    def record_synthesis(self, latency_ms: int):
        """Record synthesis performance metrics."""
        self.metrics["synthesis_latency"].append(latency_ms)
        
        logger.info(
            "Synthesis performance recorded",
            latency_ms=latency_ms
        )
    
    def record_total(self, latency_ms: int):
        """Record total query processing time."""
        self.metrics["total_latency"].append(latency_ms)
        
        logger.info(
            "Total performance recorded",
            latency_ms=latency_ms
        )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        summary = {}
        
        for metric_name, values in self.metrics.items():
            if values:
                summary[metric_name] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "p95": sorted(values)[int(len(values) * 0.95)] if len(values) > 0 else 0
                }
            else:
                summary[metric_name] = {"count": 0}
        
        return summary
    
    def reset_metrics(self):
        """Reset all collected metrics."""
        for key in self.metrics:
            self.metrics[key] = []
        
        logger.info("Performance metrics reset")


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create the global performance monitor instance."""
    global _performance_monitor
    
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    
    return _performance_monitor


def initialize_observability():
    """
    Initialize all observability components.
    
    This function should be called at application startup to set up
    LangSmith tracing, OpenTelemetry, and performance monitoring.
    """
    
    logger.info("Initializing observability components")
    
    # Set up LangSmith tracing
    langsmith_handler = setup_langsmith_tracing()
    
    # Set up OpenTelemetry (optional)
    otel_tracer = setup_opentelemetry()
    
    # Initialize performance monitor
    performance_monitor = get_performance_monitor()
    
    logger.info(
        "Observability initialization completed",
        langsmith_enabled=langsmith_handler is not None,
        opentelemetry_enabled=otel_tracer is not None,
        performance_monitoring=True
    )
    
    return {
        "langsmith_handler": langsmith_handler,
        "otel_tracer": otel_tracer,
        "performance_monitor": performance_monitor
    }
