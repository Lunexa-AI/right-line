# RightLine MVP Architecture (Lightweight Edition)

## 0) Product Promise (Non-Negotiables)
- **< 2.0s P95** end-to-end response on low bandwidth for short queries.
- **Cited, traceable answers** every time; zero speculation.
- **WhatsApp-first UX**, with simple Web fallback.
- **Zero user PII by default**, opt-in feedback; all responses traceable to sources.
- **Runs on a $5–10 VPS**; minimal dependencies.

## 1) High-Level Architecture
```
           ┌────────────────────────────────────┐
           │              Channels              │
           │ WhatsApp | Web (Static HTML/JS)     │
           └──────────────┬─────────────────────┘
                          │
                     ┌────▼────┐
                     │  FastAPI │  Single Service
                     │   App    │  (No Gateway/Orchestrator split)
                     └────┬────┘
                          │
      ┌───────────────────▼──────────────────────┐
      │        Core RAG Pipeline (In-Process)    │
      │ - Query Processing                        │
      │ - Hybrid Search (FTS + pgvector)         │  
      │ - (Optional) Score Fusion Rerank         │
      │ - Two-Stage Compose (Extractive → LLM)   │
      └─────────┬────────────────────────────────┘
                │
        ┌───────▼─────────┐
        │  PostgreSQL      │
        │  with pgvector   │
        │  - documents     │
        │  - chunks        │
        │  - embeddings    │
        │  - queries log   │
        └───────┬──────────┘
                │
         ┌──────▼───────────┐
         │  Ingestion       │
         │  (CLI Script)    │
         │  - Crawl ZimLII  │
         │  - Parse HTML    │
         │  - Chunk & Embed │
         └──────────────────┘
```

## 2) Core Components (Truly Minimal)
### 2.1 Channels
- **WhatsApp**: Meta Cloud API webhook to `/webhook` endpoint
- **Web**: Static `index.html` served from `/` endpoint

### 2.2 Single FastAPI Service
- **File**: `services/api/main.py` (already exists)
- **Endpoints**: 
  - `/v1/query` - Main query endpoint
  - `/v1/feedback` - User feedback
  - `/webhook` - WhatsApp webhook
  - `/` - Web UI
- **No separate services**: Everything runs in one process for MVP

### 2.3 Ingestion (CLI Scripts)
- **Scripts** (to be created):
  - `scripts/ingest.py` - Main ingestion orchestrator
  - `scripts/parse_docs.py` - Parse & chunk
  - `scripts/generate_embeddings.py` - Embeddings with sentence-transformers
- **Process**: Run manually or via cron, not a service
- **Already exists**: `scripts/crawl_zimlii.py` for fetching documents

### 2.4 RAG Pipeline (In-Process)
- **Implementation**: `services/api/retrieval.py` + `services/api/composer.py`
- **Retrieval**:
  1. Query normalize (lowercase, legal tokens)
  2. Search: PostgreSQL FTS + pgvector similarity
  3. Fusion: Simple score combination (no heavy reranker in MVP)
  4. Temporal filter if date is present
- **Composition (Two-Stage)**:
  - Stage A (Extractive, sub-200ms):
    - Build a structured answer object:
      - `tldr` (≤220 chars)
      - `key_points` (3–5 bullets, ≤25 words each)
      - `citations` ([main section, optional corroborator])
      - `suggestions` (2–3 follow-ups)
  - Stage B (Local LLM rewrite, ≤600ms):
    - Backend: `llama-cpp-python` (CPU)
    - Model: TinyLlama 1.1B Chat or Phi-3-mini-instruct (GGUF Q4_K_M)
    - Prompt: Strict JSON schema to rewrite `tldr` and `key_points` for clarity/tone; preserve citations; generate context-aware suggestions
    - Params: temperature=0.2, top_p=0.9, max_tokens=120, timeout=600ms
  - Fallback: If Stage B times out/errors, return Stage A as final
- **Confidence-aware behavior**:
  - High: answer directly
  - Medium: answer + 1 clarifying question
  - Low: ask clarifying question first (no answer)

### 2.5 Data Model (PostgreSQL Only)
```sql
CREATE EXTENSION IF NOT EXISTS vector;
-- documents/chunks/embeddings as defined in init-rag.sql
```

### 2.6 Rendering (Channel-Specific)
- **WhatsApp**:
  - Title: “Act §Section — Topic”
  - TL;DR line
  - 3–5 concise bullets
  - Citations list: [1] main, [2] optional corroborator
  - Follow-ups: “1 Steps · 2 Penalties · 3 Exceptions”
- **Web**:
  - Card layout: TL;DR stripe, Key points list
  - Collapsible Details with the most relevant paragraph highlighted
  - Citations with hover preview; copy/share buttons
  - Follow-up chips to continue the conversation

## 3) Implementation Status
- **Phase 1 ✅**: Hardcoded responses complete (36 topics)
- **Phase 2 🔴**: RAG + Local LLM (answer composer) next

## 4) Deployment (Actual MVP)
- **Docker Compose**: `api` + `postgres`; mount `./models:/models`
- **Env**: `RIGHTLINE_LLM_MODEL_PATH=/models/<file>.gguf`, `RIGHTLINE_LLM_MAX_TOKENS=120`

## 5) Non-Functional Requirements
- **Latency**: P95 <2s (Retrieval ≤800ms; LLM compose ≤600ms; glue ≤200ms)
- **Security**: API key auth, rate limiting, HMAC user IDs
- **Monitoring**: Basic structlog
- **Cost**: $5/month VPS
