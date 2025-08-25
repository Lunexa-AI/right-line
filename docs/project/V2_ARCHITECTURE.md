# Gweta V2 Architecture (Production Extension)

> **Note**: This V2 builds on the lightweight MVP in `MVP_ARCHITECTURE.md`. Start with MVP for proof-of-concept, then add V2 features for production scaling, resilience, and advanced RAG. Objectives: Maintain low-latency (<1s P95), security, traceability, cost-effectiveness; scale to 1000 QPS.

## 0) Product Promise (Enhanced for V2)
- **< 1.0s P95** with edge optimization.
- **Exact + contextual summaries** with multi-modal support (e.g., diagram extraction).
- **Multi-channel** (WhatsApp, Telegram, Web PWA, USSD).
- **Zero PII**, advanced telemetry with consent.
- **Scales to $100/month cluster** for high load.

## 1) High-Level Architecture
```
// Expanded diagram with V2 additions
           ┌─────────────────────────────────────────────────────────────┐
           │                         Channels                             │
           │WhatsApp | Telegram | Web (PWA) | USSD                        │
           └──────────────┬───────────────────────────────┬───────────────┘
                          │                               │
                     ┌────▼────┐                     ┌─────▼────┐
                     │  API    │  REST/gRPC          │  Realtime│  WebSocket/PubSub
                     │ Gateway │  (CDN/WAF)          │  (Kafka)  │
                     └────┬────┘                     └─────┬────┘
                          │                                   │
                ┌─────────▼────────────────┐                  │
                │         Orchestrator     │                  │
                │  (FastAPI/K8s Pods)      │                  │
                │  – Intelligent Routing   │                  │
                │  – Advanced Guardrails   │                  │
                │  – Dynamic Policies      │                  │
                └─────────┬───────┬────────┘                  │
                          │       │                           │
      ┌───────────────────▼─┐   ┌─▼───────────────────────────▼────────┐
      │ Retrieval Service    │   │  Answer Compose + Summariser         │
      │ (Scaled)             │   │  (LLM Cluster: Llama 8B + API)      │
      │ Hybrid + Graph Query │   │  – Multilingual + Explanations      │
      │ Milvus for Vectors   │   │  – Adaptive Templates                │
      └─────────┬───────────┘   └───────────────────────────┬──────────┘
                │                                           │
        ┌───────▼─────────┐                         ┌───────▼───────────┐
        │  Indexes         │                         │   Evaluator       │
        │  - Meilisearch   │                         │  (Automated + HITL)│
        │  - Milvus Cluster│                         │  A/B, Drift Detect  │
        │  - pgvector HA   │                         │                     │
        └───────┬──────────┘                         └────────┬──────────┘
                │                                            │
         ┌──────▼───────────┐                         ┌──────▼───────────┐
         │  Document Store  │                         │  Telemetry & Ops │
         │  Postgres (AZ)   │                         │  Full Stack: Prom, │
         │  w/ Replicas     │                         │  Grafana, Loki,    │
         └──────┬───────────┘                         │  Tempo, Sentry     │
                │                                      └────────┬─────────┘
         ┌──────▼────────────────────────────┐                  │
         │    Ingestion Pipeline             │                  │
         │  (Arq/Celery, Scaled Workers)     │                  │
         │  - ML-Enhanced Scraping/OCR       │                  │
         │  - Knowledge Graph (Neo4j)        │                  │
         │  - Auto-Versioning + Diffs        │                  │
         └──────┬────────────────────────────┘                  │
                │                                              │
         ┌──────▼──────────┐                            ┌───────▼──────────┐
         │  Object Store   │                            │  Backup & DR      │
         │  S3/MinIO       │                            │  (Multi-Region,    │
         │  (Replicated)   │                            │   Automated)       │
         └─────────────────┘                            └──────────────────┘
```

## 2) Core Components (V2 Extensions)
### 2.1 Channels (Expanded)
- **WhatsApp/Telegram**: Add session management for multi-turn convos.
- **Web PWA**: Offline caching, service workers.
- **USSD**: Menu-driven queries via aggregator API.
**Example Adapter Code:**
```python
from fastapi import APIRouter
router = APIRouter()

@router.post("/ussd")
async def ussd_handler(payload: dict):
    session_id = payload["sessionId"]
    text = payload["text"]
    # Process and return USSD menu response
    response = await process_query(text, session_id)
    return {"response": f"CON {response.summary}\n1. More details\n2. Related"}
```

// Continue expanding each section with code, configs, etc.
// For Milvus: Detailed setup
### 2.2.2 Milvus Integration (V2 Vector Store)
- Use Milvus for scalable vector search; migrate from pgvector in MVP.
**Setup Example (Docker):**
```yaml
services:
  milvus:
    image: milvusdb/milvus:latest
    ports:
      - "19530:19530"
    volumes:
      - milvus_data:/milvus/data
```
**Python Client Code:**
```python
from pymilvus import connections, CollectionSchema, FieldSchema, DataType, Collection

connections.connect("default", host="localhost", port="19530")

fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),
    FieldSchema(name="metadata", dtype=DataType.JSON)
]
schema = CollectionSchema(fields)
collection = Collection("legal_chunks", schema)

collection.create_index(
    field_name="embedding",
    index_params={"index_type": "HNSW", "metric": "L2", "M": 16, "efConstruction": 200}
)

# Insertion example
entities = [
    [1],  # id
    [[0.1] * 384],  # embedding
    [{"section": "1A"}]  # metadata
]
collection.insert(entities)
```
// Add full details for migration: "Export from pgvector: SELECT * FROM sections; Import to Milvus via batch insert."

// Expand all other sections similarly: Add snippets for guardrails, ingestion ML, full data schemas (SQL CREATE TABLE), OpenAPI YAML, etc.
// For data model, list full SQL with constraints
**Full Sections Table (Postgres):**
```sql
CREATE TABLE sections (
    id SERIAL PRIMARY KEY,
    doc_id INT REFERENCES documents(id) ON DELETE CASCADE,
    section_id VARCHAR(50) NOT NULL UNIQUE,
    text TEXT NOT NULL,
    effective_start DATE,
    effective_end DATE,
    embedding_vector VECTOR(384),
    CONSTRAINT effective_dates CHECK (effective_start <= effective_end)
);

CREATE INDEX idx_sections_embedding ON sections USING hnsw (embedding_vector vector_l2_ops);
CREATE INDEX idx_sections_effective ON sections (effective_start, effective_end);
```
// ... continue for all tables

// Add sections for Migration Guide from MVP
## 18) Migration from MVP to V2
1. **Database**: Add replicas to Postgres; migrate vectors to Milvus cluster.
   - Script: `scripts/migrate_vectors.py` - Query pgvector, batch insert to Milvus.
2. **Services**: Deploy as K8s pods; add Arq for queues.
3. **Config**: Update .env with Milvus creds, enable advanced features via flags.
// ... detailed steps

// Ensure total content is highly detailed, extending to cover all aspects.
// ... existing code from original, expanded ...
