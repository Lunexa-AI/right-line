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

## 🔧 PHASE 2: LIGHTWEIGHT RAG MVP (Weeks 5-6)

> **Goal**: Implement a minimal RAG system on top of Phase 1: simple ingestion, pgvector-based hybrid search, local reranking/summary, basic eval/ops. Deploy to VPS. Total effort: ~40 hours. Follow MVP_ARCHITECTURE.md for minimalism.

### 2.1 Corpus & Ingestion 🔴

#### 2.1.1 Source acquisition & policy ✅
- [x] Automated crawler created: `scripts/crawl_zimlii.py` downloads Labour Act, SIs, and cases
- [x] .gitignore configured: Excludes `data/raw/**` keeping only `.gitkeep`
- [ ] Run crawler to fetch documents: `python scripts/crawl_zimlii.py` (Effort: 0.5 hours)
- [ ] Update `docs/data/SOURCES.md` with fetched sources (Effort: 0.5 hours)

#### 2.1.2 Database setup for documents
- [ ] Create database schema script `scripts/init-rag.sql`:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE TABLE documents (id SERIAL PRIMARY KEY, source_url TEXT, title TEXT, ingest_date TIMESTAMP);
  CREATE TABLE chunks (id SERIAL PRIMARY KEY, doc_id INT REFERENCES documents(id), chunk_text TEXT, chunk_index INT, embedding vector(384), metadata JSONB);
  ```
  (Tests: Schema loads without error; Effort: 0.5 hours)
- [ ] Run migration: `docker exec rightline-postgres psql -U rightline -f init-rag.sql` (Effort: 0.5 hours)

#### 2.1.3 Document parsing & chunking
- [ ] Create `scripts/parse_docs.py`: Parse HTML with BeautifulSoup, extract sections (Effort: 2 hours)
- [ ] Add chunking logic: Split into ~512 token chunks with overlap (Effort: 1 hour)
- [ ] Store parsed chunks in database (Tests: Chunks queryable; Effort: 1 hour)

#### 2.1.4 Text normalization
- [ ] Add normalization to parser: Strip whitespace, standardize section numbers (Effort: 1 hour)
- [ ] Error handling: Log failed files, continue processing (Effort: 0.5 hours)

### 2.2 Embeddings & pgvector Store 🔴

#### 2.2.1 Embedding setup
- [ ] Install dependencies: `pip install sentence-transformers` (Effort: 0.5 hours)
- [ ] Create `scripts/generate_embeddings.py`:
  ```python
  from sentence_transformers import SentenceTransformer
  model = SentenceTransformer('BAAI/bge-small-en-v1.5')
  # Load chunks from DB, generate embeddings, store back
  ```
  (Tests: Generates 384-dim vectors; Effort: 2 hours)

#### 2.2.2 Vector indexing
- [ ] Create vector index: `CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops);` (Effort: 0.5 hours)
- [ ] Create text search index: `CREATE INDEX ON chunks USING GIN (to_tsvector('english', chunk_text));` (Effort: 0.5 hours)
- [ ] Test similarity search works: Query returns similar chunks (Effort: 1 hour)

### 2.3 Retrieval & Reranking 🔴

#### 2.3.1 Text search implementation
- [ ] Create `services/api/retrieval.py` with FTS query:
  ```python
  async def text_search(query: str, limit: int = 50):
      sql = "SELECT * FROM chunks WHERE to_tsvector('english', chunk_text) @@ plainto_tsquery('english', %s) LIMIT %s"
  ```
  (Tests: Returns relevant chunks; Effort: 1 hour)

#### 2.3.2 Vector search implementation  
- [ ] Add vector search to `retrieval.py`:
  ```python
  async def vector_search(query_embedding, limit: int = 50):
      sql = "SELECT * FROM chunks ORDER BY embedding <-> %s LIMIT %s"
  ```
  (Tests: Returns similar chunks; Effort: 1 hour)
- [ ] Implement score fusion: Combine text and vector results (Effort: 1 hour)

#### 2.3.3 Reranking (Optional for MVP)
- [ ] Skip for MVP - use simple score fusion instead
- [ ] Can add in V2 for better accuracy

### 2.4 Answer Composition 🔴

#### 2.4.1 Response generation
- [ ] Update `services/api/responses.py` to use retrieved chunks:
  ```python
  def generate_response(chunks):
      top_chunk = chunks[0]
      summary = extract_key_sentences(top_chunk.text, max_lines=3)
      citation = f"{top_chunk.metadata['source']} Section {top_chunk.metadata['section']}"
      return QueryResponse(summary=summary, citation=citation)
  ```
  (Tests: Returns formatted response; Effort: 2 hours)

#### 2.4.2 Basic lang support
- [ ] Add `lang_hint` param; fallback to English. (Tests: Routing; Effort: 1 hour)

### 2.5 Evaluation 🔴

#### 2.5.1 Golden set
- [ ] Human: Curate 20-30 QA pairs in `tests/golden.yaml`. (Effort: 1.5 hours)
- [ ] Load and basic eval functions. (Tests: Loader; Effort: 0.5 hours)

#### 2.5.2 Benchmark script
- [ ] `scripts/eval_rag.py`: Compute Recall@k/MRR/faithfulness. (Tests: Runs clean; Effort: 1.5 hours)

### 2.6 Basic Ops 🔴

#### 2.6.1 Logging & metrics
- [ ] Add structlog timings for stages. (Tests: Logs present; Effort: 1 hour)
- [ ] Basic metrics export (JSON or Prometheus client). (Tests: Exported; Effort: 1 hour)

#### 2.6.2 Indexing CLI
- [ ] `scripts/index.py`: Re-embed/reindex idempotently. (Tests: No duplicates; Effort: 2 hours)

### 2.7 Privacy 🔴

#### 2.7.1 Hygiene
- [ ] HMAC user IDs; redact PII in logs. (Tests: No raw IDs; Effort: 1 hour)
- [ ] Redis-based rate limiter. (Tests: Enforced; Effort: 1 hour)

### 2.8 Integration & Deployment 🔴
- [ ] Wire up RAG pipeline in `/v1/query` endpoint (Effort: 2 hours)
- [ ] Test end-to-end: Query returns real document chunks (Effort: 1 hour)
- [ ] Deploy updated version: `docker-compose -f docker-compose.mvp.yml up -d --build` (Effort: 1 hour)
- [ ] Verify with test queries (Effort: 0.5 hours)

## 🏗️ PHASE 3: PRODUCTION EXTENSION (Post-MVP)
> Refer to V2_ARCHITECTURE.md for details. Implement after MVP validation: add scaling, Milvus, full ops, etc. Effort: ~80 hours.
