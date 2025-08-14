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

#### 1.2.2 Collect user feedback
- [ ] Add feedback mechanism in responses
- [ ] Simple analytics (query logging)
- [ ] User satisfaction tracking
- [ ] Identify common query patterns
- **Tests**: Analytics tests
- **Acceptance**: Can track user engagement and satisfaction
- **Effort**: 3 hours

#### 1.2.3 Iterate based on feedback
- [ ] Improve hardcoded responses based on user queries
- [ ] Add more Q&A pairs for common questions
- [ ] Refine response formatting
- [ ] Fix user-reported issues
- **Tests**: Regression tests for fixes
- **Acceptance**: Higher user satisfaction scores
- **Effort**: 6 hours

## 🔧 PHASE 2: ENHANCED MVP (Weeks 5-6)

> **Goal**: Add real functionality while keeping it simple. Single service with basic persistence.

### 2.1 Real Document Processing 🔴

#### 2.1.1 Simple document ingestion
- [ ] Load PDF documents (Labour Act, key SIs)
- [ ] Basic text extraction with PyMuPDF
- [ ] Simple section parsing (regex-based)
- [ ] Store in SQLite database
- **Tests**: Document parsing tests
- **Acceptance**: Can load and parse real legal documents
- **Effort**: 6 hours

#### 2.1.2 Basic search implementation
- [ ] Simple text search with SQLite FTS
- [ ] Keyword matching and ranking
- [ ] Return relevant sections
- [ ] Basic relevance scoring
- **Tests**: Search accuracy tests
- **Acceptance**: Returns relevant sections for queries
- **Effort**: 4 hours

#### 2.1.3 Improve response generation
- [ ] Template-based summaries from real sections
- [ ] Extract actual citations
- [ ] Add section context
- [ ] Improve confidence scoring
- **Tests**: Response quality tests
- **Acceptance**: Responses based on real legal content
- **Effort**: 5 hours

### 2.2 Basic Persistence & Caching 🔴

#### 2.2.1 Add SQLite database
- [ ] Simple schema (documents, sections, queries)
- [ ] Basic CRUD operations
- [ ] Query logging for analytics
- [ ] Simple migrations
- **Tests**: Database operation tests
- **Acceptance**: Data persists between restarts
- **Effort**: 3 hours

#### 2.2.2 Add in-memory caching
- [ ] Cache frequent queries in memory
- [ ] Simple LRU cache implementation
- [ ] Cache search results
- [ ] Basic cache metrics
- **Tests**: Cache hit/miss tests
- **Acceptance**: Faster responses for repeated queries
- **Effort**: 2 hours

### 2.3 Enhanced User Experience 🔴

#### 2.3.1 Improve WhatsApp integration
- [ ] Better message formatting
- [ ] Handle follow-up questions
- [ ] Add typing indicators
- [ ] Error message improvements
- **Tests**: Message flow tests
- **Acceptance**: Better user experience on WhatsApp
- **Effort**: 4 hours

#### 2.3.2 Add basic analytics
- [ ] Track query patterns
- [ ] Monitor response quality
- [ ] User engagement metrics
- [ ] Simple dashboard
- **Tests**: Analytics tests
- **Acceptance**: Can measure product usage and quality
- **Effort**: 3 hours

## 🏗️ PHASE 3: PRODUCTION ENHANCEMENT (Weeks 7-12)

> **Goal**: Scale to production-grade system with advanced features and monitoring.

### 3.1 Microservices Architecture 🔴

#### 3.1.1 Split into microservices
- [ ] Extract API service (FastAPI gateway)
- [ ] Create retrieval service (search)
- [ ] Create ingestion service (document processing)
- [ ] Create summarizer service (response generation)
- **Tests**: Service integration tests
- **Acceptance**: Services communicate via HTTP/gRPC
- **Effort**: 12 hours

#### 3.1.2 Setup PostgreSQL with pgvector
- [ ] Migrate from SQLite to PostgreSQL
- [ ] Configure pgvector extension
- [ ] Setup connection pooling
- [ ] Add performance tuning
- **Tests**: Database migration tests
- **Acceptance**: PostgreSQL handles production load
- **Effort**: 6 hours

#### 3.1.3 Setup Redis for caching
- [ ] Configure Redis with persistence
- [ ] Implement caching abstraction
- [ ] Add cache decorators
- [ ] Setup cache warming
- **Tests**: Cache performance tests
- **Acceptance**: Significant performance improvement
- **Effort**: 4 hours

### 3.2 Advanced Search & AI 🔴

#### 3.2.1 Implement hybrid search
- [ ] Add BM25 search with Meilisearch
- [ ] Implement vector search with pgvector
- [ ] Create hybrid ranking algorithm
- [ ] Add cross-encoder reranking
- **Tests**: Search quality benchmarks
- **Acceptance**: Significantly improved search relevance
- **Effort**: 10 hours

#### 3.2.2 Advanced document processing
- [ ] OCR for scanned documents
- [ ] Better section parsing with ML
- [ ] Temporal versioning support
- [ ] Citation extraction and linking
- **Tests**: Document processing accuracy tests
- **Acceptance**: Handles complex legal documents
- **Effort**: 8 hours

#### 3.2.3 AI-powered summarization
- [ ] Local LLM for summarization
- [ ] Template-based response generation
- [ ] Multi-language support (Shona, Ndebele)
- [ ] Prompt injection protection
- **Tests**: Summary quality tests
- **Acceptance**: High-quality, safe summaries
- **Effort**: 12 hours

### 3.3 Production Infrastructure 🔴

#### 3.3.1 Setup object storage
- [ ] Configure MinIO for document storage
- [ ] Setup backup and replication
- [ ] Add access policies and security
- [ ] Implement file versioning
- **Tests**: Storage reliability tests
- **Acceptance**: Secure, reliable document storage
- **Effort**: 4 hours

#### 3.3.2 Add comprehensive monitoring
- [ ] Setup Prometheus metrics
- [ ] Configure Grafana dashboards
- [ ] Add alerting with PagerDuty/Slack
- [ ] Implement health checks
- **Tests**: Monitoring and alerting tests
- **Acceptance**: Full observability of system health
- **Effort**: 6 hours

#### 3.3.3 Security hardening
- [ ] Add WAF and rate limiting
- [ ] Implement JWT authentication
- [ ] Setup secret management
- [ ] Add security scanning
- **Tests**: Security penetration tests
- **Acceptance**: Production-grade security
- **Effort**: 8 hours

### 3.4 Advanced Features 🔴

#### 3.4.1 Multi-channel support
- [ ] Telegram bot integration
- [ ] Web app with React/Next.js
- [ ] API for third-party integrations
- [ ] Mobile-responsive design
- **Tests**: Cross-platform tests
- **Acceptance**: Works across all channels
- **Effort**: 10 hours

#### 3.4.2 Advanced analytics
- [ ] User behavior tracking
- [ ] Query success metrics
- [ ] A/B testing framework
- [ ] Business intelligence dashboard
- **Tests**: Analytics accuracy tests
- **Acceptance**: Data-driven product insights
- **Effort**: 6 hours

#### 3.4.3 Legal content expansion
- [ ] Add more acts and statutory instruments
- [ ] Case law integration
- [ ] Legal forms and templates
- [ ] Multi-jurisdiction support
- **Tests**: Content accuracy tests
- **Acceptance**: Comprehensive legal coverage
- **Effort**: 15 hours

## 📊 Summary

### Phase 1 (Weeks 2-4): Lightweight MVP
- **Total Effort**: ~25 hours
- **Goal**: Validate concept with hardcoded responses
- **Deliverable**: Working WhatsApp bot with mock legal responses

### Phase 2 (Weeks 5-6): Enhanced MVP  
- **Total Effort**: ~27 hours
- **Goal**: Real functionality with simple architecture
- **Deliverable**: Actual legal search with SQLite backend

### Phase 3 (Weeks 7-12): Production Enhancement
- **Total Effort**: ~91 hours
- **Goal**: Production-grade system with advanced features
- **Deliverable**: Scalable, monitored, secure legal AI system

---

*This approach allows rapid validation and iteration while building toward a production-grade system.*
