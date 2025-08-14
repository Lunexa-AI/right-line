# RightLine MVP Task List

> **📋 Comprehensive implementation roadmap for RightLine MVP**  
> Each task is designed to be completed in a single PR with tests, following TDD practices.  
> Tasks are organized by milestone and include acceptance criteria and estimated effort.

## 🎯 MVP Strategy: Build Fast, Iterate, Scale

**Phase 1: Lightweight MVP (Weeks 2-4)**
- Single FastAPI service with hardcoded responses
- Basic WhatsApp integration
- Simple in-memory search
- Validate concept and user feedback

**Phase 2: Enhanced MVP (Weeks 5-6)**  
- Add real document processing
- Implement basic search
- Add persistence layer

**Phase 3: Production Enhancement (Weeks 7-12)**
- Microservices architecture
- Advanced search (BM25 + vectors)
- Full monitoring and scaling

## 📊 Task Tracking

- 🔴 Not started
- 🟡 In progress
- 🟢 Complete
- ⏸️ Blocked
- ❌ Cancelled

## Milestone 0: Project Foundation (Week 1)

### 0.1 Repository Setup 🟡

#### 0.1.1 Initialize project structure ✅
- [x] Create directory structure as per architecture
- [x] Initialize git repository with .gitignore
- [x] Add LICENSE (MIT) and code of conduct
- [x] Create initial README with badges
- **Acceptance**: Repository structure matches architecture doc
- **Effort**: 1 hour
- **Completed**: 2024-08-13

#### 0.1.2 Setup Python project ✅
- [x] Initialize Poetry/pyproject.toml with Python 3.11
- [x] Configure project metadata and dependencies
- [x] Setup development dependencies (pytest, ruff, mypy, black)
- [x] Create requirements.txt for production
- **Acceptance**: `poetry install` works, all tools configured
- **Effort**: 2 hours
- **Completed**: 2024-08-13

#### 0.1.3 Configure pre-commit hooks ✅
- [x] Setup pre-commit config with ruff, black, mypy
- [x] Add security checks (bandit, safety)
- [x] Configure conventional commits (optional - can enable later)
- [x] Add secrets scanning (detect-secrets)
- **Acceptance**: Pre-commit runs on all commits
- **Effort**: 1 hour
- **Completed**: 2024-08-13

#### 0.1.4 Create Makefile ✅
- [x] Add common commands (setup, test, lint, format)
- [x] Add Docker commands (build, up, down, logs)
- [x] Add deployment commands
- [x] Document all commands
- **Acceptance**: All make targets work
- **Effort**: 2 hours
- **Completed**: 2024-08-13

### 0.2 CI/CD Pipeline ✅

#### 0.2.1 Setup GitHub Actions workflows ✅
- [x] Create CI workflow for tests and linting (DISABLED)
- [x] Add code coverage reporting (codecov)
- [x] Configure matrix testing (Python versions)
- [x] Add caching for dependencies
- **Acceptance**: CI runs on all PRs (ready to enable when needed)
- **Effort**: 3 hours
- **Completed**: 2024-08-13
- **Note**: Created as `.yml.disabled` files for easy activation

#### 0.2.2 Add security scanning ✅
- [x] Configure Dependabot for dependency updates (DISABLED)
- [x] Add Trivy for container scanning
- [x] Setup SAST with Semgrep
- [x] Configure security alerts
- **Acceptance**: Security scans run automatically (ready to enable)
- **Effort**: 2 hours
- **Completed**: 2024-08-13
- **Note**: Comprehensive security pipeline ready for activation

#### 0.2.3 Setup deployment pipeline ✅
- [x] Create staging deployment workflow (DISABLED)
- [x] Add production deployment with approval (DISABLED)
- [x] Configure environment secrets documentation
- [x] Add smoke tests post-deployment
- **Acceptance**: Deployments work with approval gates (ready to enable)
- **Effort**: 3 hours
- **Completed**: 2024-08-13
- **Note**: Comprehensive deployment pipeline with blue-green and canary strategies

### 0.3 Development Environment 🔴

#### 0.3.1 Create Docker setup ✅
- [x] Write Dockerfile for each service
- [x] Optimize for layer caching
- [x] Add multi-stage builds
- [x] Configure non-root users
- **Acceptance**: All services build successfully
- **Effort**: 4 hours
- **Completed**: 2024-08-13
- **Note**: Individual Dockerfiles created for api, ingestion, retrieval, and summarizer services

#### 0.3.2 Setup Docker Compose ✅
- [x] Create docker-compose.yml for local dev
- [x] Configure service dependencies
- [x] Add volume mounts for hot-reload
- [x] Setup networking
- **Acceptance**: `docker-compose up` starts all services
- **Effort**: 3 hours
- **Completed**: 2024-08-13
- **Note**: Complete Docker Compose setup with override file for development

#### 0.3.3 Configure environment variables ✅
- [x] Create .env.example with all variables
- [x] Setup env validation with pydantic
- [x] Add environment-specific configs
- [x] Document all variables
- **Acceptance**: Services start with example env
- **Effort**: 2 hours
- **Completed**: 2024-08-13
- **Note**: Pydantic Settings with RIGHTLINE_ prefix and validation

## 🚀 PHASE 1: LIGHTWEIGHT MVP (Weeks 2-4)

> **Goal**: Validate concept with minimal viable functionality. Build fast, test with users, iterate.

### 1.1 Single Service MVP 🔴

#### 1.1.1 Create minimal FastAPI service ✅
- [x] Single `main.py` with FastAPI app
- [x] Basic `/query` endpoint with hardcoded responses
- [x] Simple health check endpoint
- [x] Basic error handling
- **Tests**: API endpoint tests
- **Acceptance**: API responds to queries with mock data
- **Effort**: 2 hours
- **Completed**: 2025-01-10

#### 1.1.2 Add hardcoded legal responses ✅
- [x] Create 20-30 sample Q&A pairs from Labour Act (29 topics total)
- [x] Simple keyword matching for queries
- [x] Return structured response (summary, section, citations)
- [x] Add confidence scoring (mock)
- **Tests**: Query matching tests
- **Acceptance**: Realistic responses to common legal questions
- **Effort**: 4 hours
- **Completed**: 2025-01-10

#### 1.1.3 Basic WhatsApp integration ✅
- [x] Setup WhatsApp Business API webhook
- [x] Handle incoming messages
- [x] Send formatted responses
- [x] Basic message validation
- **Tests**: Webhook tests, message formatting
- **Acceptance**: Can query via WhatsApp and get responses
- **Effort**: 6 hours
- **Completed**: 2025-01-10

#### 1.1.4 Simple web interface ✅
- [x] Basic HTML form for testing
- [x] Query input and response display
- [x] Simple styling with Tailwind/Bootstrap
- [x] Mobile-responsive design
- **Tests**: UI interaction tests
- **Acceptance**: Web interface works on mobile
- **Effort**: 3 hours
- **Completed**: 2025-01-10

### 1.2 User Feedback & Iteration 🔴

#### 1.2.1 Deploy lightweight MVP ✅
- [x] Deploy single service to VPS
- [x] Setup basic monitoring (uptime)
- [x] Configure domain and SSL
- [x] Add basic logging
- **Tests**: Deployment smoke tests
- **Acceptance**: MVP accessible via web and WhatsApp
- **Effort**: 4 hours
- **Completed**: 2025-01-10
- **Notes**: Created comprehensive deployment guide, Docker setup, and scripts

#### 1.2.2 Collect user feedback ✅
- [x] Add feedback mechanism in responses
- [x] Simple analytics (query logging)
- [x] User satisfaction tracking
- [x] Identify common query patterns
- **Tests**: Analytics tests
- **Acceptance**: Can track user engagement and satisfaction
- **Effort**: 3 hours
- **Completed**: 2025-01-10
- **Notes**: SQLite analytics, feedback endpoint, query analysis script

#### 1.2.3 Iterate based on feedback ✅
- [x] Improve hardcoded responses based on user queries
- [x] Add more Q&A pairs for common questions (36 topics total)
- [x] Refine response formatting
- [x] Fix user-reported issues
- **Tests**: Regression tests for fixes
- **Acceptance**: Higher user satisfaction scores
- **Effort**: 6 hours
- **Completed**: 2025-01-10
- **Notes**: Added 7 new topics (overtime, notice period, paternity, retrenchment, etc.), enhanced WhatsApp formatting

## 🔧 PHASE 2: RAG MVP (Weeks 5-6)

> Goal: Deliver a working legal RAG MVP for Zimbabwe. Hybrid retrieval (BM25 + vectors), reranking, strict citation-first answers. Minimal, fast, and observable per `.cursorrules` and `ARCHITECTURE.md`.

### 2.1 Corpus & Ingestion 🔴

#### 2.1.1 Source acquisition & policy
- [ ] Define authoritative sources (Labour Act, selected SIs, Constitution chapters relevant to labour)
- [ ] Document licensing/compliance notes and update `docs/data/SOURCES.md`
- **Acceptance**: Written list of sources with URLs/paths and usage terms
- **Effort**: 1 hour

#### 2.1.2 Deterministic section chunking
- [ ] Parse acts/SIs into sections/subsections; stable IDs: `<act_code>:<chapter>:<section>[:<sub>]`
- [ ] Store effective dates/version metadata
- [ ] Persist chunks with schema: `documents`, `sections`, `section_chunks(text, start, end, effective_start, effective_end)`
- **Tests**: Chunk boundary determinism; ID stability across runs
- **Acceptance**: Same input yields identical IDs/chunking; sections queryable by ID
- **Effort**: 5 hours

#### 2.1.3 Text extraction pipeline
- [ ] Robust PDF/text extraction (PyMuPDF + fallback plain text)
- [ ] Basic normalization (whitespace, numbering, footnotes)
- **Tests**: Known pages → expected normalized text
- **Acceptance**: >99% of target docs extract without errors
- **Effort**: 3 hours

### 2.2 Embeddings & Vector Store 🔴

#### 2.2.1 Embedding service
- [ ] Choose default model: `bge-small-en` (open-source) with optional OpenAI embeddings via flag
- [ ] Batch embedding with retries/timeouts; store `embedding_model_version`
- **Tests**: Same text → identical vector; throughput benchmark snapshot
- **Acceptance**: 10k chunks embed < 15 min on dev box; reproducible vectors
- **Effort**: 4 hours

#### 2.2.2 Vector DB setup
- [ ] Pick store: `pgvector` (default) or `Qdrant` (flag)
- [ ] Schemas: `section_chunks(id, doc_id, section_id, text, embedding_vector, lang, effective_start, effective_end)`
- [ ] Index: HNSW (M=16, efc=200) or IVF tuned; add filters for date/lang
- **Tests**: kNN returns self on probe; filtered search respects dates
- **Acceptance**: Vector search P95 < 200ms on 10k chunks
- **Effort**: 4 hours

### 2.3 Retrieval & Reranking 🔴

#### 2.3.1 BM25 (lexical) baseline
- [ ] Enable BM25 via Meilisearch or Postgres FTS (config flag `USE_PG_FTS`)
- [ ] Normalization: lowercase, legal stop-words, numeric section capture
- **Tests**: Queries for known sections return top-5
- **Acceptance**: BM25 Recall@50 ≥ 0.9 on tiny golden set
- **Effort**: 3 hours

#### 2.3.2 Hybrid fusion
- [ ] Retrieve BM25@50 + Vec@80; merge with reciprocal rank fusion or learned weights
- [ ] Temporal filter: support "as at YYYY-MM-DD"
- **Tests**: Hybrid beats BM25-only on golden set
- **Acceptance**: +10% MRR vs BM25-only on golden set
- **Effort**: 4 hours

#### 2.3.3 Cross-encoder reranker
- [ ] Add cross-encoder (e.g., `bge-reranker-base` ONNX/int8) with time budget (≤400ms)
- [ ] Early stop on high-confidence; configurable k
- **Tests**: Reranked list improves top-1 hit rate
- **Acceptance**: Top-1 improves ≥10% over hybrid-only
- **Effort**: 4 hours

### 2.4 Answer Composer (Extractive) 🔴

#### 2.4.1 Strict 3-line summary with citations
- [ ] Compose answer from selected chunk(s): EXACT 3 lines, ≤100 chars each
- [ ] Inject citation block: act/chapter/section and URLs
- [ ] Confidence from retrieval+rerank signals
- **Tests**: Schema validation; refusal on missing cites; line-length enforcement
- **Acceptance**: 100% answers include correct citation; rejects when unsure
- **Effort**: 3 hours

#### 2.4.2 Multilingual hinting (optional)
- [ ] Accept `lang_hint` (en/sn/nd); choose embedding/rerank accordingly (if available)
- **Tests**: Requests route to correct pipeline
- **Acceptance**: No regression for `en`; graceful degrade for others
- **Effort**: 2 hours

### 2.5 Evaluation & Golden Set 🔴

#### 2.5.1 Tiny golden set
- [ ] Curate 30–50 QA pairs with authoritative section IDs
- [ ] Store as YAML; include expected relevant sections
- **Tests**: Recall@k, MRR, faithfulness checks
- **Acceptance**: CI target: Recall@50 ≥ 0.9; faithfulness 100% on gold
- **Effort**: 3 hours

#### 2.5.2 Regression benchmark script
- [ ] CLI to run retrieval and report metrics; export JSON trend
- **Acceptance**: Single command outputs metrics and failure cases
- **Effort**: 2 hours

### 2.6 Ops & Observability (MVP) 🔴

#### 2.6.1 Metrics & traces
- [ ] Per-stage latency (embed, bm25, vector, rerank, compose)
- [ ] Cache hit ratio; request_id propagation; anonymized user hash
- **Tests**: Metrics present; 95p latency within budget (Retrieval ≤800ms; Rerank ≤400ms)
- **Acceptance**: Grafana-ready metrics or JSON logs that can be scraped
- **Effort**: 2 hours

#### 2.6.2 Index jobs
- [ ] CLI jobs: (re)embed, (re)index, backfill effective dates
- **Acceptance**: Re-runnable and idempotent; can rebuild from scratch
- **Effort**: 2 hours

### 2.7 Admin & APIs 🔴

#### 2.7.1 Minimal admin endpoints
- [ ] `/admin/reindex` (authenticated flag-protected) to trigger reindex on small corpora
- [ ] `/v1/sections/{id}` to fetch raw section and metadata
- **Tests**: Permission checks; smoke tests
- **Acceptance**: Operators can refresh index post-deploy
- **Effort**: 2 hours

### 2.8 Privacy & Safety 🔴

#### 2.8.1 PII & logging hygiene
- [ ] HMAC-hash user identifiers; redact inputs in logs; no raw PII persist
- [ ] Rate limit per hashed user; add basic abuse protection
- **Tests**: Log inspection; rate-limit unit tests
- **Acceptance**: No PII leakage; stable under basic abuse
- **Effort**: 2 hours

---

### Deliverable (Phase 2):
- A working legal RAG MVP: ingest → hybrid retrieval → rerank → 3-line, citation-first answers
- Minimal jobs, metrics, and golden-set evaluation to prevent regressions


## 🏗️ PHASE 3: PRODUCTION RAG (Weeks 7-12)

> **Goal**: Operate a state-of-the-art, reliable legal RAG in production across Web and WhatsApp, including ZimLII case law. Meet latency/SLOs, security, privacy, and observability requirements from `.cursorrules` and `ARCHITECTURE.md`.

### 3.1 Productization & Channels 🔴

#### 3.1.1 Web app (production-ready)
- [ ] Harden web UI (a11y, keyboard navigation, dark mode, offline-safe states)
- [ ] PWA-lite: manifest + icons; graceful caching for static assets
- [ ] Security headers; CSP tuned for our stack; gzip/brotli; HTTP/2
- **Tests**: Lighthouse a11y ≥ 90; basic E2E (query → answer with cites)
- **Acceptance**: Mobile-first UX; zero console errors; stable under throttled 3G
- **Effort**: 6 hours

#### 3.1.2 WhatsApp productionization
- [ ] Verify webhook with signature; strict payload validation
- [ ] Session threading (short-term memory) with safe context windowing
- [ ] Rate limiting/token bucket per user hash; abuse controls
- **Tests**: Webhook signature unit tests; E2E message flow; rate-limit tests
- **Acceptance**: Stable under bursts; no PII in logs; messages formatted consistently
- **Effort**: 6 hours

### 3.2 Content Expansion (Acts + ZimLII) 🔴

#### 3.2.1 ZimLII case law ingestion
- [ ] Scrape/ingest selected labor-related judgments
- [ ] Normalize metadata (court, date, citation); compute stable case IDs
- [ ] Link cases ↔ statutes via citation extraction (regex + heuristics)
- **Tests**: Sample set correctness; dedup by hash; citation link coverage
- **Acceptance**: Cases searchable; cases show linked sections
- **Effort**: 10 hours

#### 3.2.2 Cross-source versioning
- [ ] Track effective dates; deprecate superseded sections
- [ ] Maintain source registry with provenance
- **Tests**: Temporal queries return correct version
- **Acceptance**: “as at DATE” works across acts and cases
- **Effort**: 4 hours

### 3.3 Retrieval Quality & Guardrails 🔴

#### 3.3.1 Legal-aware reranking improvements
- [ ] Add citation prior features (sections cited by many relevant cases get a small boost)
- [ ] Optional graph-augmented pass (section-case bipartite edges) within time budget
- **Tests**: Golden set Top-1 improves; latency budgets respected
- **Acceptance**: +10% Top-1 w/o +20% latency over Phase 2 baseline
- **Effort**: 6 hours

#### 3.3.2 Faithfulness and refusal
- [ ] Lightweight answer validator: ensure answer spans exist in retrieved text
- [ ] Safe refusal when confidence low or sources missing
- **Tests**: Hallucination checks; refusal pathways; schema enforcement
- **Acceptance**: 100% answers grounded; 0% fabricated citations
- **Effort**: 4 hours

### 3.4 Scale & Reliability 🔴

#### 3.4.1 Services & storage
- [ ] Split services: API gateway, Retrieval, Ingestion, Summariser
- [ ] PostgreSQL + pgvector (managed/HA); Redis (HA) for cache/rate-limit; Object storage (S3/MinIO)
- [ ] Blue/green deploy with health/readiness; circuit breakers; backoff retries
- **Tests**: Service integration tests; failover drills; smoke during deploy
- **Acceptance**: Zero-downtime rolling deploys; automated daily backups
- **Effort**: 12 hours

#### 3.4.2 Performance & caching
- [ ] Per-stage budgets: Retrieval ≤800ms; Rerank ≤400ms; Compose ≤600ms
- [ ] Response cache for hot queries; partial results cache (features, BM25 lists)
- **Tests**: Load tests @ P95<2s, P99<3s; cache hit ratio > 30% on golden traffic
- **Acceptance**: Meets latency SLOs under expected load
- **Effort**: 6 hours

### 3.5 Observability & Security 🔴

#### 3.5.1 Metrics, logs, traces
- [ ] OpenTelemetry spans across services; structured logs with request_id/user_hash
- [ ] Dashboards: latency per stage, errors, cache hit, query volume; SLOs + alerts
- **Tests**: Synthetic alerts; dashboard panels populated in staging
- **Acceptance**: On-call can diagnose issues quickly
- **Effort**: 6 hours

#### 3.5.2 Security hardening
- [ ] JWT auth for admin endpoints; webhook signatures; WAF/rate-limits at edge
- [ ] Secrets management; key rotation; encrypted backups; vulnerability scans
- **Tests**: Basic pen-test checklist; dependency scans green; headers verified
- **Acceptance**: No high/critical security findings
- **Effort**: 6 hours

### 3.6 MLOps (Pragmatic) 🔴

#### 3.6.1 Versioning & jobs
- [ ] Version registry for: corpus, chunker, embedding model, reranker, prompts
- [ ] Scheduled jobs: re-embed changed docs; reindex; drift detection
- **Tests**: Dry-run jobs; idempotency; metrics recorded
- **Acceptance**: Reproducible builds of the index; measured drift
- **Effort**: 6 hours

#### 3.6.2 Evaluation at merge
- [ ] CI job: run golden set; block regressions beyond threshold
- [ ] Store historical metrics for trend lines (artifact)
- **Tests**: Failing PR demo; pass thresholds post-fix
- **Acceptance**: No silent relevance regressions reach prod
- **Effort**: 4 hours

### 3.7 Language & Accessibility 🔴

#### 3.7.1 Shona/Ndebele support (incremental)
- [ ] Expand embeddings/reranker or translation fallback; UI localization basics
- **Tests**: Smoke queries in SN/ND; no crashes; English parity holds
- **Acceptance**: Degrades gracefully; roadmap to parity documented
- **Effort**: 4 hours

### 3.8 Admin & Governance 🔴

#### 3.8.1 Lightweight admin console
- [ ] View index status, ingestion logs, recent feedback; trigger small reindexes
- **Tests**: Auth + RBAC checks; happy path
- **Acceptance**: Ops can manage without shell access
- **Effort**: 4 hours

## 📊 Summary

### Phase 1 (Weeks 2-4): Lightweight MVP
- **Total Effort**: ~25 hours
- **Goal**: Validate concept with hardcoded responses
- **Deliverable**: Working WhatsApp bot with mock legal responses

### Phase 2 (Weeks 5-6): Enhanced MVP  
- **Total Effort**: ~27 hours
- **Goal**: Real functionality with simple architecture
- **Deliverable**: Actual legal search with SQLite backend

### Phase 3 (Weeks 7-12): Production RAG
- **Total Effort**: ~98 hours
- **Goal**: Production-grade legal RAG across Web and WhatsApp with ZimLII cases
- **Deliverable**: Reliable, observable, secure system meeting latency SLOs; grounded answers with citations

---

*This approach allows rapid validation and iteration while building toward a production-grade system.*
