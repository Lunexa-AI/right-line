"""
HTTP Bridge for LangGraph Studio to communicate with RightLine API.

This file creates a simple LangGraph that makes HTTP requests to our
running FastAPI server, avoiding dependency conflicts between Studio
and our main application.
"""

from __future__ import annotations

import asyncio
import json
from typing import List, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

# Only import what Studio needs - no project dependencies
try:
    import httpx
except ImportError:
    # Fallback if httpx not available in Studio environment
    import urllib.request
    import urllib.parse
    httpx = None


class StudioGraphState(TypedDict):
    """State for the LangGraph Studio wrapper graph."""
    messages: List[BaseMessage]


async def call_rightline_api(state: StudioGraphState) -> dict:
    """
    Make HTTP request to our running RightLine API server.
    This avoids dependency conflicts by keeping systems separate.
    """
    messages = state['messages']
    
    # Extract the last human message as the query
    query_text = ""
    for message in messages:
        if isinstance(message, HumanMessage):
            query_text = message.content.strip()
    
    if not query_text:
        ai_message = AIMessage(content="Hello! How can I help you with Zimbabwe legal questions?")
        return {"messages": messages + [ai_message]}
    
    try:
        # Make HTTP request to our running API
        api_url = "http://localhost:8000/api/v1/test-query"
        payload = {"query": query_text, "top_k": 3}
        
        if httpx:
            # Use httpx if available (preferred)
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(api_url, json=payload)
                response.raise_for_status()
                result = response.json()
        else:
            # Fallback to urllib (synchronous)
            import urllib.request
            import urllib.parse
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                api_url, 
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
        
        # Format the response for Studio UI
        if result.get('synthesis'):
            synthesis = result['synthesis']
            content = f"""**🏛️ Legal Analysis**

**Summary:** {synthesis.get('tldr', 'No summary available')}

**Key Points:**
{chr(10).join(f"• {point}" for point in synthesis.get('key_points', []))}

**Confidence:** {synthesis.get('confidence', 0.0):.1%}
**Query Time:** {result.get('query_time_ms', 0)}ms
**Sources Found:** {len(result.get('results', []))} documents

**Retrieved Documents:**
{chr(10).join(f"📄 {doc.get('title', 'Unknown')} (Score: {doc.get('confidence', 0):.2f})" for doc in result.get('results', [])[:3])}
"""
        else:
            # Fallback to raw retrieval results
            results = result.get('results', [])
            if results:
                content = f"""**📚 Document Search Results**

Found {len(results)} relevant documents:

{chr(10).join(f"📄 **{doc.get('title', 'Unknown Document')}**{chr(10)}   {doc.get('content', '')[:200]}..." for doc in results[:2])}

**Query Time:** {result.get('query_time_ms', 0)}ms
**Status:** {result.get('status', 'completed')}
"""
            else:
                content = "No relevant legal documents found for your query."
        
        ai_message = AIMessage(content=content)
        return {"messages": messages + [ai_message]}
        
    except Exception as e:
        # Handle connection errors gracefully
        error_content = f"""**⚠️ Connection Error**

Could not connect to RightLine API server.

**Error:** {str(e)}

**Troubleshooting:**
• Make sure the RightLine API is running on http://localhost:8000
• Start the API with: `source venv/bin/activate && uvicorn api.main:app --reload`
• Check that port 8000 is not blocked

**Query:** {query_text}
"""
        
        error_message = AIMessage(content=error_content)
        return {"messages": messages + [error_message]}


# Create the LangGraph StateGraph
def create_studio_graph():
    """Create the LangGraph StateGraph for Studio."""
    
    workflow = StateGraph(StudioGraphState)
    
    # Add the HTTP bridge node
    workflow.add_node("rightline_api_bridge", call_rightline_api)
    
    # Set entry and exit points
    workflow.set_entry_point("rightline_api_bridge")
    workflow.add_edge("rightline_api_bridge", END)
    
    # Compile the graph
    return workflow.compile()


# Export the graph for LangGraph Studio
graph = create_studio_graph()


def get_graph():
    """Allow Studio to discover the graph."""
    return graph