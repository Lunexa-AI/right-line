# RightLine MVP Architecture (Lightweight Edition)

## 0) Product Promise (Non-Negotiables)
- **< 2.0s P95** end-to-end response on low bandwidth for short queries.
- **Exact section + 3-line summary + citations** every time; no hallucinations.
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
      │ - Reranking (Optional for MVP)           │
      │ - Summary Generation (Extractive)        │
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
  - `scripts/embed.py` - Generate embeddings using sentence-transformers
  - `scripts/chunk.py` - Text chunking logic
- **Process**: Run manually or via cron, not a service
- **Already exists**: `scripts/crawl_zimlii.py` for fetching documents

### 2.4 RAG Pipeline (In-Process)
- **Implementation**: Add to `services/api/retrieval.py` (new file)
- **Components**:
  1. Query processor: Basic normalization
  2. Search: PostgreSQL FTS + pgvector similarity
  3. Fusion: Simple score combination
  4. Summary: Extract key sentences (no LLM needed for MVP)
- **No external services**: No Meilisearch, Qdrant, or Redis needed

### 2.5 Data Model (PostgreSQL Only)
```sql
-- Single database with pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    source_url TEXT,
    title TEXT,
    ingest_date TIMESTAMP DEFAULT NOW()
);

CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    doc_id INT REFERENCES documents(id),
    chunk_text TEXT,
    chunk_index INT,
    embedding vector(384),  -- bge-small-en dimension
    metadata JSONB
);

CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON chunks USING GIN (to_tsvector('english', chunk_text));
```

## 3) Implementation Status
- **Phase 1 ✅**: Hardcoded responses complete (36 topics)
- **Phase 2 🔴**: RAG implementation needed (this is the next step)
- **Current State**: FastAPI service running with hardcoded responses

## 4) Deployment (Actual MVP)
- **Docker Compose**: Only 2 containers needed
  - `api`: FastAPI service
  - `postgres`: PostgreSQL with pgvector
- **No need for**: Redis, Meilisearch, Qdrant, MinIO, Nginx
- **Resources**: 2GB RAM VPS sufficient

## 5) Non-Functional Requirements
- **Latency**: P95 <2s (achievable with in-process pipeline)
- **Security**: API key auth, rate limiting, HMAC user IDs
- **Monitoring**: Basic structlog, no complex observability needed
- **Cost**: $5/month VPS handles ~100 concurrent users
