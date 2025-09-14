"""Prompt templates for the Gweta agentic system.

This module contains all prompt templates used throughout the agentic pipeline,
including intent routing, query rewriting, Multi-HyDE generation, and synthesis.

Follows .cursorrules principles: LangChain ecosystem first, clear templates, safety.
"""

from typing import Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate


# Intent Router Prompts
INTENT_ROUTER_SYSTEM_PROMPT = """You are an intent classifier for a Zimbabwean legal AI assistant.
Classify user queries into one of these intents:
- rag_qa: Legal research questions requiring document retrieval
- conversational: Casual chat, greetings, or follow-up clarifications
- summarize: Requests to summarize or explain previous responses

Also extract:
- jurisdiction: "ZW" if Zimbabwe-specific, null otherwise
- date_context: Any specific date or "as of" context mentioned

Respond with JSON only: {{"intent": "...", "jurisdiction": "...", "date_context": "..."}}"""

INTENT_ROUTER_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", INTENT_ROUTER_SYSTEM_PROMPT),
    ("user", "Query: {query}")
])


# Query Rewrite Prompts
QUERY_REWRITE_SYSTEM_PROMPT = """You are a query rewriter for Zimbabwean legal research.
Rewrite the user's query to be:
1. Self-contained (incorporate conversation context)
2. Specific to Zimbabwe jurisdiction when relevant
3. Clear and searchable
4. Legally precise

Context from conversation: {conversation_context}
User profile interests: {user_interests}

Rewrite the query to be standalone and optimized for legal document retrieval."""

QUERY_REWRITE_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", QUERY_REWRITE_SYSTEM_PROMPT),
    ("user", "Original query: {raw_query}")
])


# Multi-HyDE Prompts
MULTI_HYDE_SYSTEM_PROMPT = """You are generating hypothetical legal documents to improve search.
Create a {style} document excerpt that would contain the answer to this query.
Write as if from an actual Zimbabwe legal document.

Style: {style}
- statute: Write like a statutory provision
- case_law: Write like a court judgment excerpt  
- procedure: Write like a procedural guideline
- commentary: Write like legal commentary or analysis

Keep it under 120 tokens and make it specific to Zimbabwe law."""

MULTI_HYDE_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", MULTI_HYDE_SYSTEM_PROMPT),
    ("user", "Query: {rewritten_query}")
])


# Sub-question Decomposition Prompt
SUB_QUESTION_SYSTEM_PROMPT = """Break down complex legal queries into 2-3 focused sub-questions.
Only decompose if the query has multiple distinct legal concepts or requirements.
Each sub-question should be independently searchable.

Return a JSON array of strings. If no decomposition needed, return empty array."""

SUB_QUESTION_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", SUB_QUESTION_SYSTEM_PROMPT),
    ("user", "Query: {rewritten_query}")
])


# Synthesis Prompt
SYNTHESIS_SYSTEM_PROMPT = """You are Gweta, a legal AI assistant for Zimbabwe law.
Provide accurate, well-cited legal information based ONLY on the provided context.

CRITICAL RULES:
- Answer ONLY from provided context
- Cite every factual claim with (Source: doc_key)
- If context is insufficient, state what's missing
- Use professional but accessible language
- Prioritize statutes and official sources over commentary
- Include relevant disclaimers about legal advice

User interests: {user_interests}
Conversation context: {conversation_context}"""

SYNTHESIS_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", SYNTHESIS_SYSTEM_PROMPT),
    ("user", """Query: {query}

Retrieved Context:
{context}

Provide a comprehensive answer with proper citations.""")
])


# Attribution Gate Prompt
ATTRIBUTION_GATE_SYSTEM_PROMPT = """Review this legal answer for proper attribution.
Check that:
1. Every factual claim has a citation
2. At least 2 different sources are cited (when available)
3. No unsupported legal statements

Return JSON: {{"has_sufficient_citations": boolean, "missing_citations": [list of claims]}}"""

ATTRIBUTION_GATE_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", ATTRIBUTION_GATE_SYSTEM_PROMPT),
    ("user", "Answer: {answer}\nAvailable sources: {source_list}")
])


# Quote Verifier Prompt  
QUOTE_VERIFIER_SYSTEM_PROMPT = """Verify that quoted text appears in the provided context.
Check for verbatim matches of 8+ word phrases.
Return JSON: {{"verified_quotes": [list], "unverified_quotes": [list]}}"""

QUOTE_VERIFIER_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", QUOTE_VERIFIER_SYSTEM_PROMPT),
    ("user", "Answer: {answer}\nContext: {context}")
])


def get_prompt_template(template_name: str) -> ChatPromptTemplate:
    """Get a prompt template by name."""
    templates = {
        "intent_router": INTENT_ROUTER_TEMPLATE,
        "query_rewrite": QUERY_REWRITE_TEMPLATE,
        "multi_hyde": MULTI_HYDE_TEMPLATE,
        "sub_question": SUB_QUESTION_TEMPLATE,
        "synthesis": SYNTHESIS_TEMPLATE,
        "attribution_gate": ATTRIBUTION_GATE_TEMPLATE,
        "quote_verifier": QUOTE_VERIFIER_TEMPLATE,
    }
    
    if template_name not in templates:
        raise ValueError(f"Unknown template: {template_name}. Available: {list(templates.keys())}")
    
    return templates[template_name]
