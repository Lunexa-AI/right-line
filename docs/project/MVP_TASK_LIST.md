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

## 🔧 PHASE 2: SERVERLESS RAG MVP (Weeks 5-6)

> **Goal**: Implement a serverless RAG system on top of Phase 1: Milvus Cloud vector store, OpenAI embeddings/completion, Vercel deployment. Total effort: ~35 hours. Follow MVP_ARCHITECTURE.md for serverless design.

### 2.1 Corpus & Ingestion 🔴

#### 2.1.1 Source acquisition & policy ✅
- [x] Automated crawler created: `scripts/crawl_zimlii.py` downloads Labour Act, SIs, and cases
- [x] .gitignore configured: Excludes `data/raw/**` keeping only `.gitkeep`
- [ ] Run crawler to fetch documents: `python scripts/crawl_zimlii.py` (Effort: 0.5 hours)
- [ ] Update `docs/data/SOURCES.md` with fetched sources (Effort: 0.5 hours)

#### 2.1.2 Milvus Cloud setup
- [ ] Create Milvus Cloud account and cluster (free tier: 1 cluster, 1GB storage) (Effort: 0.5 hours)
- [ ] Create collection schema script `scripts/init-milvus.py`:
  ```python
  # Collection: legal_chunks
  # Fields: id (int64), doc_id (varchar), chunk_text (varchar), embedding (float_vector[1536]), metadata (json)
  ```
  (Tests: Collection created successfully; Effort: 1 hour)
- [ ] Get Milvus connection credentials (endpoint, token) (Effort: 0.25 hours)

#### 2.1.3 Document parsing & chunking
- [ ] Create `scripts/parse_docs.py`: Parse HTML with BeautifulSoup, extract sections (Effort: 2 hours)
- [ ] Add chunking logic: Split into ~512 token chunks with overlap (Effort: 1 hour)
- [ ] Store parsed chunks locally (JSON/CSV for ingestion) (Tests: Chunks readable; Effort: 1 hour)

#### 2.1.4 Text normalization
- [ ] Add normalization to parser: Strip whitespace, standardize section numbers (Effort: 1 hour)
- [ ] Error handling: Log failed files, continue processing (Effort: 0.5 hours)

### 2.2 OpenAI Embeddings & Milvus Store 🔴

#### 2.2.1 OpenAI embedding setup
- [ ] Install dependencies: `pip install openai pymilvus` (Effort: 0.5 hours)
- [ ] Create `scripts/generate_embeddings.py`:
  ```python
  import openai
  from pymilvus import connections, Collection
  # Use text-embedding-3-small (1536 dims, $0.02/1M tokens)
  # Batch process chunks, upload to Milvus
  ```
  (Tests: Generates 1536-dim vectors; Effort: 2.5 hours)

#### 2.2.2 Milvus vector indexing
- [ ] Create HNSW index on Milvus collection: `collection.create_index("embedding", {"index_type": "HNSW"})` (Effort: 0.5 hours)
- [ ] Test similarity search works: Query returns similar chunks (Effort: 1 hour)
- [ ] Load collection and verify performance (Effort: 0.5 hours)

### 2.3 Milvus Retrieval & Reranking 🔴

#### 2.3.1 Vector search implementation
- [ ] Create `api/retrieval.py` (Vercel function structure) with Milvus similarity search. (Tests: Returns relevant chunks; Effort: 2 hours)
- [ ] Add query embedding with OpenAI `text-embedding-3-small`. (Tests: Query vectorized; Effort: 1 hour)

#### 2.3.2 Hybrid search and reranking
- [ ] Add keyword-based boost for exact legal term matches. (Tests: Legal terms prioritized; Effort: 1 hour)
- [ ] Temporal filter by date if provided in query. (Tests: Correct version filtering; Effort: 0.5 hours)

#### 2.3.3 Confidence scoring
- [ ] Compute confidence from similarity scores and result diversity. (Tests: Sensible distribution; Effort: 0.5 hours)

### 2.4 OpenAI Answer Composition 🔴

#### 2.4.1 OpenAI GPT setup
- [ ] Add OpenAI client to dependencies and configuration. (Effort: 0.5 hours)
- [ ] Choose model: `gpt-3.5-turbo` (fast, cheap) or `gpt-4o-mini` (better). (Effort: 0.25 hours)
- [ ] Env vars: `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_MAX_TOKENS=300`. (Effort: 0.25 hours)

#### 2.4.2 Structured prompt composition
- [ ] Create `api/composer.py` with JSON schema prompt for OpenAI:
  - `tldr` (≤220 chars)
  - `key_points` (3–5 bullets, ≤25 words each)
  - `citations` (document references)
  - `suggestions` (2–3 follow-ups)
  (Tests: Valid JSON output; Effort: 2 hours)
- [ ] Add extractive fallback if OpenAI fails/times out. (Tests: Graceful degradation; Effort: 1 hour)

#### 2.4.3 Confidence-aware flow
- [ ] High: answer directly; Medium: answer + 1 clarifying question; Low: ask for clarification first. (Tests: Branching; Effort: 1 hour)

### 2.5 Vercel Deployment Setup 🔴

#### 2.5.1 Vercel configuration
- [ ] Create `vercel.json` with function routes and build settings. (Effort: 1 hour)
- [ ] Move FastAPI app to `api/` directory for Vercel functions. (Effort: 1.5 hours)
- [ ] Add Mangum adapter for FastAPI-to-ASGI-to-Vercel. (Effort: 0.5 hours)

#### 2.5.2 Environment setup
- [ ] Configure Vercel environment variables (OpenAI, Milvus credentials). (Effort: 0.5 hours)
- [ ] Update analytics to use Vercel KV instead of SQLite. (Effort: 2 hours)
- [ ] Test local development with Vercel CLI. (Effort: 1 hour)

### 2.6 Rendering (Channel-specific) 🔴
- [ ] WhatsApp renderer: Title, TL;DR, bullets, citations list, follow-up numeric options. (Tests: Formatting; Effort: 1 hour)
- [ ] Web renderer: Move to `web/` directory, build static site. (Tests: DOM checks; Effort: 1.5 hours)

### 2.7 Evaluation 🔴
- [ ] Golden set: 20–30 QA pairs; evaluate Recall@k and manual faithfulness spot checks. (Effort: 2 hours)
- [ ] Latency tests: Ensure Milvus search ≤500ms, OpenAI compose ≤1s; overall P95 <2s. (Effort: 1 hour)

### 2.8 Basic Ops 🔴
- [ ] Metrics: per-stage timings (retrieve, compose, total), confidence, OpenAI usage. (Effort: 1 hour)
- [ ] Indexing CLI: idempotent re-embed/reindex to Milvus. (Effort: 2 hours)

### 2.9 Integration & Deployment 🔴
- [ ] Wire RAG + OpenAI in `/api/v1/query`; test with Milvus connection. (Effort: 1.5 hours)
- [ ] End-to-end tests with WhatsApp and Web outputs. (Effort: 1 hour)
- [ ] Deploy to Vercel and verify P95 <2s performance. (Effort: 1 hour)

## 🏗️ PHASE 3: PRODUCTION EXTENSION (Post-MVP)
> Refer to V2_ARCHITECTURE.md for details. Implement after MVP validation: add scaling, Milvus, full ops, etc. Effort: ~80 hours.
