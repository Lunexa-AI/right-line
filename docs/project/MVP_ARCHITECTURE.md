# Gweta MVP Architecture (Vercel + Milvus Edition)

## 0) Product Promise (Non-Negotiables)
- **< 2.0s P95** end-to-end response on low bandwidth for short queries.
- **Cited, traceable answers** every time; zero speculation.
- **Dual channel UX**: Enterprise Web workbench + citizen WhatsApp chatbot.
- **Zero user PII by default**, opt-in feedback; all responses traceable to sources.
- **Serverless deployment** on Vercel; pay-per-use scaling.

## 1) High-Level Architecture
```
           ┌────────────────────────────────────┐
           │              Channels              │
           │ Web (Enterprise) | WhatsApp (Citizens) │
           └──────────────┬─────────────────────┘
                          │
                   ┌──────▼──────┐
                   │   Vercel    │  Serverless Functions
                   │  Functions  │  (FastAPI via Mangum)
                   └──────┬──────┘
                          │
      ┌───────────────────▼──────────────────────┐
      │        Core RAG Pipeline (Serverless)    │
      │ - Query Processing                        │
      │ - Vector Search (Milvus Cloud)           │
      │ - Hybrid Retrieval + Reranking           │
      │ - OpenAI GPT-3.5/4 Composition           │
      └─────────┬────────────────────────────────┘
                │
        ┌───────▼─────────┐
        │  Milvus Cloud    │
        │  Vector Store    │
        │  - documents     │
        │  - chunks        │
        │  - embeddings    │
        └───────┬──────────┘
                │
         ┌──────▼───────────┐
         │  OpenAI APIs     │
         │  - text-embedding-3-small │
         │  - gpt-3.5-turbo │
         │  - (gpt-4o-mini) │
         └──────────────────┘
```

## 2) Core Components (Serverless)
### 2.1 Channels
- **Gweta Web (Enterprise)**: Evidence‑first research workbench (RAG search with citations). Deployed as a static site with serverless APIs. Grows into agentic tooling (tool calling, drafting, web search).
- **Gweta WhatsApp (Citizens)**: Free chatbot for ordinary citizens. “Get the smart lawyer friend you always wanted.” Meta Cloud API webhook → `/api/webhook`.

### 2.2 Vercel Functions (FastAPI)
- **File**: `api/main.py` (Vercel API routes)
- **Adapter**: Mangum for FastAPI-to-ASGI-to-Vercel
- **Endpoints**: 
  - `/api/v1/query` - Main query endpoint
  - `/api/v1/feedback` - User feedback (stored in Vercel KV)
  - `/api/webhook` - WhatsApp webhook
- **Scaling**: Auto-scaling serverless functions

### 2.3 Ingestion (Local/GitHub Actions)
- **Scripts** (run locally or in CI):
  - `scripts/ingest.py` - Main ingestion orchestrator
  - `scripts/parse_docs.py` - Parse & chunk documents
  - `scripts/generate_embeddings.py` - OpenAI embeddings + Milvus upload
- **Process**: Run locally, then push embeddings to Milvus Cloud
- **Already exists**: `scripts/crawl_zimlii.py` for fetching documents

### 2.4 RAG Pipeline (Serverless)
- **Implementation**: `api/retrieval.py` + `api/composer.py`
- **Retrieval**:
  1. Query normalize (lowercase, legal tokens)
  2. Embedding: OpenAI `text-embedding-3-small` (1536 dims)
  3. Vector Search: Milvus Cloud similarity search (top-k=20)
  4. Reranking: Simple score-based or keyword boost
  5. Temporal filter if date provided
- **Composition (OpenAI)**:
  - Model: `gpt-3.5-turbo` (fast, cheap) or `gpt-4o-mini` (better quality)
  - Prompt: Structured JSON schema for:
    - `tldr` (≤220 chars)
    - `key_points` (3–5 bullets, ≤25 words each)
    - `citations` (document references)
    - `suggestions` (2–3 follow-ups)
  - Params: temperature=0.2, max_tokens=300, timeout=10s
  - Fallback: If OpenAI fails, return extractive summary
- **Confidence-aware behavior**:
  - High: answer directly
  - Medium: answer + 1 clarifying question
  - Low: ask clarifying question first (no answer)

### 2.5 Data Stores
- **Vector Store**: Milvus Cloud (managed)
- **Analytics**: Vercel KV (Redis-compatible)
- **Session**: Stateless (no persistent sessions)

```python
# Milvus Collection Schema
{
    "collection_name": "legal_chunks",
    "fields": [
        {"name": "id", "type": "int64", "is_primary": True},
        {"name": "doc_id", "type": "varchar", "max_length": 100},
        {"name": "chunk_text", "type": "varchar", "max_length": 5000},
        {"name": "embedding", "type": "float_vector", "dim": 1536},
        {"name": "metadata", "type": "json"}
    ]
}
```

### 2.6 Rendering (Channel-Specific)
- **WhatsApp (Citizens)**:
  - Title: "Act §Section — Topic"
  - TL;DR line
  - 3–5 concise bullets
  - Citations list: [1] main, [2] optional corroborator
  - Follow-ups: "1 Steps · 2 Penalties · 3 Exceptions"
- **Web (Enterprise)**:
  - Omnibox + streamed answers; less‑ink answer cards (TL;DR + Key points)
  - Evidence rail with numbered citations; hover previews; copy/share buttons
  - Minimal controls: feedback, translate EN/Shona, export

## 3) Implementation Status
- **Phase 1 ✅**: Hardcoded responses complete (36 topics)
- **Phase 2 🔴**: RAG + OpenAI + Milvus (serverless) next

## 4) Deployment (Vercel Serverless)
- **Platform**: Vercel (free tier: 100GB-hours/month function execution)
- **Build**: `vercel build` → static site + serverless functions
- **Env**: Vercel environment variables for OpenAI, Milvus credentials

## 5) Non-Functional Requirements
- **Latency**: P95 <2s (Milvus search ≤500ms; OpenAI compose ≤1s; overhead ≤300ms)
- **Security**: API key auth, rate limiting, HMAC user IDs
- **Monitoring**: Vercel Analytics + OpenAI usage tracking
- **Cost**: 
  - Vercel: Free tier (then $20/month Pro)
  - Milvus Cloud: $0.10/million queries (estimate $5-10/month)
  - OpenAI: $0.50/1M tokens embedding + $1.50/1M tokens GPT-3.5 (estimate $10-20/month)
