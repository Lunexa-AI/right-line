# RightLine MVP Task List

> **📋 Comprehensive implementation roadmap for RightLine MVP**  
> Each task is designed to be completed in a single PR with tests, following TDD practices.  
> Tasks are organized by milestone and include acceptance criteria and estimated effort.

## 🎯 MVP Goal

Build a functional legal information system that:
- Accepts WhatsApp/API queries in plain language
- Returns accurate statute sections with 3-line summaries
- Achieves <2.5s P95 latency
- Runs on a $10/month VPS
- Handles Labour Act + selected SIs initially

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

#### 0.1.3 Configure pre-commit hooks
- [ ] Setup pre-commit config with ruff, black, mypy
- [ ] Add security checks (bandit, safety)
- [ ] Configure conventional commits
- [ ] Add secrets scanning (detect-secrets)
- **Acceptance**: Pre-commit runs on all commits
- **Effort**: 1 hour

#### 0.1.4 Create Makefile
- [ ] Add common commands (setup, test, lint, format)
- [ ] Add Docker commands (build, up, down, logs)
- [ ] Add deployment commands
- [ ] Document all commands
- **Acceptance**: All make targets work
- **Effort**: 2 hours

### 0.2 CI/CD Pipeline 🔴

#### 0.2.1 Setup GitHub Actions workflows
- [ ] Create CI workflow for tests and linting
- [ ] Add code coverage reporting (codecov)
- [ ] Configure matrix testing (Python versions)
- [ ] Add caching for dependencies
- **Acceptance**: CI runs on all PRs
- **Effort**: 3 hours

#### 0.2.2 Add security scanning
- [ ] Configure Dependabot for dependency updates
- [ ] Add Trivy for container scanning
- [ ] Setup SAST with Semgrep
- [ ] Configure security alerts
- **Acceptance**: Security scans run automatically
- **Effort**: 2 hours

#### 0.2.3 Setup deployment pipeline
- [ ] Create staging deployment workflow
- [ ] Add production deployment with approval
- [ ] Configure environment secrets
- [ ] Add smoke tests post-deployment
- **Acceptance**: Deployments work with approval gates
- **Effort**: 3 hours

### 0.3 Development Environment 🔴

#### 0.3.1 Create Docker setup
- [ ] Write Dockerfile for each service
- [ ] Optimize for layer caching
- [ ] Add multi-stage builds
- [ ] Configure non-root users
- **Acceptance**: All services build successfully
- **Effort**: 4 hours

#### 0.3.2 Setup Docker Compose
- [ ] Create docker-compose.yml for local dev
- [ ] Configure service dependencies
- [ ] Add volume mounts for hot-reload
- [ ] Setup networking
- **Acceptance**: `docker-compose up` starts all services
- **Effort**: 3 hours

#### 0.3.3 Configure environment variables
- [ ] Create .env.example with all variables
- [ ] Setup env validation with pydantic
- [ ] Add environment-specific configs
- [ ] Document all variables
- **Acceptance**: Services start with example env
- **Effort**: 2 hours

## Milestone 1: Core Infrastructure (Week 2)

### 1.1 Database Setup 🔴

#### 1.1.1 Setup PostgreSQL with pgvector
- [ ] Configure PostgreSQL 15 with pgvector extension
- [ ] Setup connection pooling with PgBouncer
- [ ] Configure performance settings
- [ ] Add health checks
- **Tests**: Connection tests, extension verification
- **Acceptance**: Database accessible, pgvector works
- **Effort**: 3 hours

#### 1.1.2 Design database schema
- [ ] Create acts, versions, sections tables
- [ ] Add section_chunks with vector column
- [ ] Design citations and cross-references
- [ ] Add indexes for performance
- **Tests**: Schema creation tests
- **Acceptance**: All tables created with proper constraints
- **Effort**: 4 hours

#### 1.1.3 Setup Alembic migrations
- [ ] Initialize Alembic configuration
- [ ] Create initial migration
- [ ] Add migration testing
- [ ] Setup rollback procedures
- **Tests**: Migration up/down tests
- **Acceptance**: Migrations run successfully
- **Effort**: 2 hours

#### 1.1.4 Create SQLAlchemy models
- [ ] Define all database models
- [ ] Add relationships and constraints
- [ ] Configure lazy loading strategies
- [ ] Add model validation
- **Tests**: Model CRUD tests
- **Acceptance**: All models work with database
- **Effort**: 4 hours

### 1.2 Cache Layer 🔴

#### 1.2.1 Setup Redis
- [ ] Configure Redis with persistence
- [ ] Setup connection pool
- [ ] Configure memory limits and eviction
- [ ] Add monitoring
- **Tests**: Connection and operation tests
- **Acceptance**: Redis accessible, data persists
- **Effort**: 2 hours

#### 1.2.2 Implement caching abstraction
- [ ] Create cache interface
- [ ] Implement Redis backend
- [ ] Add TTL management
- [ ] Add cache invalidation logic
- **Tests**: Cache hit/miss tests, TTL tests
- **Acceptance**: Caching works with proper expiry
- **Effort**: 3 hours

#### 1.2.3 Add cache decorators
- [ ] Create @cache decorator for functions
- [ ] Add cache key generation
- [ ] Implement cache warming
- [ ] Add cache metrics
- **Tests**: Decorator tests, key generation tests
- **Acceptance**: Functions cached automatically
- **Effort**: 3 hours

### 1.3 Object Storage 🔴

#### 1.3.1 Setup MinIO
- [ ] Configure MinIO container
- [ ] Create buckets for PDFs and artifacts
- [ ] Setup access policies
- [ ] Configure lifecycle rules
- **Tests**: Upload/download tests
- **Acceptance**: Files stored and retrieved
- **Effort**: 2 hours

#### 1.3.2 Implement storage abstraction
- [ ] Create storage interface
- [ ] Implement S3-compatible backend
- [ ] Add retry logic
- [ ] Add progress tracking
- **Tests**: Storage operation tests
- **Acceptance**: Files managed through abstraction
- **Effort**: 3 hours

### 1.4 Message Queue 🔴

#### 1.4.1 Setup Arq with Redis
- [ ] Configure Arq workers
- [ ] Setup job queues (high/medium/low priority)
- [ ] Add dead letter queue
- [ ] Configure retries
- **Tests**: Job enqueue/process tests
- **Acceptance**: Jobs processed asynchronously
- **Effort**: 3 hours

#### 1.4.2 Create job abstractions
- [ ] Define job base classes
- [ ] Add job serialization
- [ ] Implement job status tracking
- [ ] Add job cancellation
- **Tests**: Job lifecycle tests
- **Acceptance**: Jobs tracked and manageable
- **Effort**: 3 hours

## Milestone 2: API Foundation (Week 2-3)

### 2.1 FastAPI Setup 🔴

#### 2.1.1 Initialize FastAPI application
- [ ] Create main FastAPI app
- [ ] Configure CORS and security headers
- [ ] Setup request ID middleware
- [ ] Add exception handlers
- **Tests**: App initialization tests
- **Acceptance**: API starts and responds
- **Effort**: 2 hours

#### 2.1.2 Implement health checks
- [ ] Add /health endpoint
- [ ] Add /ready endpoint with dependency checks
- [ ] Add /metrics endpoint
- [ ] Configure liveness/readiness probes
- **Tests**: Health check tests
- **Acceptance**: All health endpoints work
- **Effort**: 2 hours

#### 2.1.3 Setup API versioning
- [ ] Implement URL versioning (/v1)
- [ ] Add version negotiation
- [ ] Configure deprecation headers
- [ ] Document versioning strategy
- **Tests**: Version routing tests
- **Acceptance**: Multiple versions coexist
- **Effort**: 2 hours

### 2.2 Authentication & Authorization 🔴

#### 2.2.1 Implement API key authentication
- [ ] Create API key model and storage
- [ ] Add authentication middleware
- [ ] Implement rate limiting per key
- [ ] Add key rotation support
- **Tests**: Auth tests, rate limit tests
- **Acceptance**: API keys required and validated
- **Effort**: 4 hours

#### 2.2.2 Add JWT support for services
- [ ] Setup JWT generation and validation
- [ ] Configure token expiry and refresh
- [ ] Add service-to-service auth
- [ ] Implement token blacklisting
- **Tests**: JWT validation tests
- **Acceptance**: Services authenticate with JWT
- **Effort**: 3 hours

### 2.3 Core API Endpoints 🔴

#### 2.3.1 Implement query endpoint
- [ ] Create POST /v1/query endpoint
- [ ] Add request validation with Pydantic
- [ ] Implement response serialization
- [ ] Add OpenAPI documentation
- **Tests**: Endpoint tests, validation tests
- **Acceptance**: Query endpoint accepts and validates requests
- **Effort**: 3 hours

#### 2.3.2 Add feedback endpoint
- [ ] Create POST /v1/feedback endpoint
- [ ] Store feedback in database
- [ ] Add feedback analytics
- [ ] Implement rate limiting
- **Tests**: Feedback storage tests
- **Acceptance**: Feedback stored and retrievable
- **Effort**: 2 hours

#### 2.3.3 Implement section endpoint
- [ ] Create GET /v1/sections/{id} endpoint
- [ ] Add section history support
- [ ] Include cross-references
- [ ] Add caching
- **Tests**: Section retrieval tests
- **Acceptance**: Sections retrieved with metadata
- **Effort**: 3 hours

### 2.4 Request Processing 🔴

#### 2.4.1 Implement request validation
- [ ] Create validation schemas
- [ ] Add input sanitization
- [ ] Implement length limits
- [ ] Add content type validation
- **Tests**: Validation edge case tests
- **Acceptance**: Invalid requests rejected properly
- **Effort**: 3 hours

#### 2.4.2 Add request middleware
- [ ] Implement request logging
- [ ] Add timing middleware
- [ ] Create request context
- [ ] Add request deduplication
- **Tests**: Middleware chain tests
- **Acceptance**: All requests tracked and timed
- **Effort**: 3 hours

## Milestone 3: Document Processing (Week 3-4)

### 3.1 Ingestion Pipeline 🔴

#### 3.1.1 Create document fetcher
- [ ] Implement HTTP fetcher with retries
- [ ] Add content hash validation
- [ ] Support resume on failure
- [ ] Add progress tracking
- **Tests**: Fetch tests with mock responses
- **Acceptance**: Documents downloaded reliably
- **Effort**: 3 hours

#### 3.1.2 Build PDF processor
- [ ] Setup PyMuPDF for text extraction
- [ ] Add OCR fallback with Tesseract
- [ ] Implement page-level processing
- [ ] Add quality scoring
- **Tests**: PDF extraction tests
- **Acceptance**: Text extracted from various PDFs
- **Effort**: 4 hours

#### 3.1.3 Implement HTML parser
- [ ] Parse Veritas HTML format
- [ ] Extract structured content
- [ ] Handle malformed HTML
- [ ] Preserve formatting
- **Tests**: HTML parsing tests
- **Acceptance**: Clean text from HTML sources
- **Effort**: 3 hours

### 3.2 Section Extraction 🔴

#### 3.2.1 Build section parser
- [ ] Implement regex-based parser
- [ ] Handle various numbering formats
- [ ] Extract section headings
- [ ] Preserve hierarchy
- **Tests**: Parser tests with edge cases
- **Acceptance**: Sections correctly identified
- **Effort**: 5 hours

#### 3.2.2 Generate stable IDs
- [ ] Create ID generation algorithm
- [ ] Handle version tracking
- [ ] Implement deduplication
- [ ] Add collision detection
- **Tests**: ID stability tests
- **Acceptance**: Consistent IDs across runs
- **Effort**: 3 hours

#### 3.2.3 Extract cross-references
- [ ] Parse citation patterns
- [ ] Build reference graph
- [ ] Validate references
- [ ] Store relationships
- **Tests**: Citation extraction tests
- **Acceptance**: References correctly linked
- **Effort**: 4 hours

### 3.3 Text Processing 🔴

#### 3.3.1 Implement text normalization
- [ ] Clean whitespace and formatting
- [ ] Normalize unicode characters
- [ ] Fix common OCR errors
- [ ] Preserve legal formatting
- **Tests**: Normalization tests
- **Acceptance**: Clean, consistent text
- **Effort**: 3 hours

#### 3.3.2 Create chunking strategy
- [ ] Implement semantic chunking
- [ ] Add overlap for context
- [ ] Respect section boundaries
- [ ] Optimize chunk sizes
- **Tests**: Chunking tests
- **Acceptance**: Meaningful chunks created
- **Effort**: 3 hours

#### 3.3.3 Add metadata extraction
- [ ] Extract effective dates
- [ ] Identify jurisdiction
- [ ] Parse amendment history
- [ ] Extract keywords
- **Tests**: Metadata extraction tests
- **Acceptance**: Rich metadata captured
- **Effort**: 3 hours

## Milestone 4: Search Implementation (Week 4-5)

### 4.1 Full-Text Search 🔴

#### 4.1.1 Setup Meilisearch
- [ ] Configure Meilisearch container
- [ ] Create indices for sections
- [ ] Configure search settings
- [ ] Add synonyms dictionary
- **Tests**: Search configuration tests
- **Acceptance**: Meilisearch operational
- **Effort**: 2 hours

#### 4.1.2 Implement BM25 indexing
- [ ] Index document chunks
- [ ] Configure ranking rules
- [ ] Add field boosting
- [ ] Setup filters
- **Tests**: Indexing tests
- **Acceptance**: Documents searchable
- **Effort**: 3 hours

#### 4.1.3 Build search client
- [ ] Create Meilisearch client wrapper
- [ ] Add retry logic
- [ ] Implement pagination
- [ ] Add faceted search
- **Tests**: Search query tests
- **Acceptance**: Search returns relevant results
- **Effort**: 3 hours

### 4.2 Vector Search 🔴

#### 4.2.1 Setup embeddings generation
- [ ] Configure sentence-transformers
- [ ] Load BGE-small model
- [ ] Implement batched encoding
- [ ] Add caching layer
- **Tests**: Embedding generation tests
- **Acceptance**: Text converted to vectors
- **Effort**: 3 hours

#### 4.2.2 Configure Qdrant
- [ ] Setup Qdrant container
- [ ] Create collections
- [ ] Configure HNSW index
- [ ] Set similarity metrics
- **Tests**: Vector storage tests
- **Acceptance**: Vectors stored and searchable
- **Effort**: 2 hours

#### 4.2.3 Implement vector indexing
- [ ] Index chunk embeddings
- [ ] Add metadata filtering
- [ ] Implement batch updates
- [ ] Add version management
- **Tests**: Vector indexing tests
- **Acceptance**: Vectors indexed with metadata
- **Effort**: 3 hours

### 4.3 Hybrid Search 🔴

#### 4.3.1 Create query parser
- [ ] Extract entities and keywords
- [ ] Detect temporal context
- [ ] Identify query intent
- [ ] Normalize query text
- **Tests**: Query parsing tests
- **Acceptance**: Queries properly analyzed
- **Effort**: 4 hours

#### 4.3.2 Implement retrieval orchestration
- [ ] Execute parallel searches
- [ ] Merge result sets
- [ ] Apply RRF fusion
- [ ] Handle timeouts
- **Tests**: Retrieval integration tests
- **Acceptance**: Combined results from both engines
- **Effort**: 4 hours

#### 4.3.3 Add reranking
- [ ] Setup cross-encoder model
- [ ] Implement scoring pipeline
- [ ] Add confidence thresholds
- [ ] Optimize for latency
- **Tests**: Reranking accuracy tests
- **Acceptance**: Results properly reranked
- **Effort**: 4 hours

## Milestone 5: Answer Generation (Week 5-6)

### 5.1 Summarization Setup 🔴

#### 5.1.1 Configure local LLM
- [ ] Setup llama.cpp server
- [ ] Load quantized model (Llama 3.2-3B)
- [ ] Configure generation params
- [ ] Add health monitoring
- **Tests**: Model loading tests
- **Acceptance**: LLM server operational
- **Effort**: 3 hours

#### 5.1.2 Create prompt templates
- [ ] Design summarization prompts
- [ ] Add output constraints
- [ ] Include few-shot examples
- [ ] Implement prompt validation
- **Tests**: Template rendering tests
- **Acceptance**: Consistent prompt formatting
- **Effort**: 3 hours

#### 5.1.3 Implement structured generation
- [ ] Use Guidance/Outlines for structure
- [ ] Enforce output format
- [ ] Add length constraints
- [ ] Handle generation errors
- **Tests**: Generation format tests
- **Acceptance**: Outputs match template
- **Effort**: 3 hours

### 5.2 Response Composition 🔴

#### 5.2.1 Build response formatter
- [ ] Create response templates
- [ ] Format for each channel
- [ ] Add citation formatting
- [ ] Include confidence scores
- **Tests**: Formatting tests per channel
- **Acceptance**: Channel-appropriate responses
- **Effort**: 3 hours

#### 5.2.2 Implement extractive fallback
- [ ] Create TextRank summarizer
- [ ] Extract key sentences
- [ ] Add sentence scoring
- [ ] Cache extractive summaries
- **Tests**: Extractive summary tests
- **Acceptance**: Fallback summaries available
- **Effort**: 3 hours

#### 5.2.3 Add response validation
- [ ] Verify citation accuracy
- [ ] Check summary length
- [ ] Validate response structure
- [ ] Add quality scoring
- **Tests**: Validation tests
- **Acceptance**: Only valid responses returned
- **Effort**: 2 hours

## Milestone 6: Channel Integration (Week 6-7)

### 6.1 WhatsApp Integration 🔴

#### 6.1.1 Setup webhook handler
- [ ] Create webhook endpoint
- [ ] Implement signature verification
- [ ] Add message parsing
- [ ] Handle delivery receipts
- **Tests**: Webhook validation tests
- **Acceptance**: WhatsApp messages received
- **Effort**: 3 hours

#### 6.1.2 Implement message sending
- [ ] Create WhatsApp client
- [ ] Format messages for WhatsApp
- [ ] Handle media messages
- [ ] Add retry logic
- **Tests**: Message sending tests
- **Acceptance**: Messages sent to WhatsApp
- **Effort**: 3 hours

#### 6.1.3 Add conversation management
- [ ] Track conversation state
- [ ] Handle multi-turn queries
- [ ] Implement timeout handling
- [ ] Add user context
- **Tests**: Conversation flow tests
- **Acceptance**: Stateful conversations work
- **Effort**: 4 hours

### 6.2 Web Interface 🔴

#### 6.2.1 Create React PWA
- [ ] Setup Next.js project
- [ ] Configure PWA manifest
- [ ] Add service worker
- [ ] Implement offline support
- **Tests**: PWA functionality tests
- **Acceptance**: App installable and works offline
- **Effort**: 4 hours

#### 6.2.2 Build chat interface
- [ ] Create message components
- [ ] Add input validation
- [ ] Implement typing indicators
- [ ] Add message history
- **Tests**: Component tests
- **Acceptance**: Chat UI functional
- **Effort**: 4 hours

#### 6.2.3 Implement API client
- [ ] Create API service layer
- [ ] Add request queuing
- [ ] Implement retry logic
- [ ] Add error handling
- **Tests**: API integration tests
- **Acceptance**: Web app communicates with API
- **Effort**: 3 hours

## Milestone 7: Testing & Quality (Week 7-8)

### 7.1 Test Infrastructure 🔴

#### 7.1.1 Setup test fixtures
- [ ] Create test database
- [ ] Add sample data fixtures
- [ ] Mock external services
- [ ] Setup test containers
- **Tests**: Fixture reliability tests
- **Acceptance**: Consistent test environment
- **Effort**: 3 hours

#### 7.1.2 Create golden dataset
- [ ] Curate 100 Q&A pairs
- [ ] Add edge cases
- [ ] Include multilingual examples
- [ ] Version control dataset
- **Tests**: Dataset validation
- **Acceptance**: Comprehensive test cases
- **Effort**: 4 hours

#### 7.1.3 Build test utilities
- [ ] Create test client factories
- [ ] Add assertion helpers
- [ ] Implement test data generators
- [ ] Add performance benchmarks
- **Tests**: Utility function tests
- **Acceptance**: Efficient test writing
- **Effort**: 3 hours

### 7.2 Integration Testing 🔴

#### 7.2.1 Test retrieval pipeline
- [ ] Test search accuracy
- [ ] Verify ranking quality
- [ ] Check latency requirements
- [ ] Test edge cases
- **Tests**: End-to-end retrieval tests
- **Acceptance**: Retrieval meets accuracy targets
- **Effort**: 4 hours

#### 7.2.2 Test answer generation
- [ ] Verify summary quality
- [ ] Check citation accuracy
- [ ] Test fallback scenarios
- [ ] Measure generation time
- **Tests**: Generation quality tests
- **Acceptance**: Summaries meet quality bar
- **Effort**: 4 hours

#### 7.2.3 Test channel integration
- [ ] Test WhatsApp flow
- [ ] Verify web interface
- [ ] Check error handling
- [ ] Test rate limiting
- **Tests**: Channel-specific tests
- **Acceptance**: All channels functional
- **Effort**: 3 hours

### 7.3 Performance Testing 🔴

#### 7.3.1 Setup load testing
- [ ] Configure Locust scripts
- [ ] Define test scenarios
- [ ] Setup monitoring
- [ ] Create reports
- **Tests**: Load test execution
- **Acceptance**: System handles target load
- **Effort**: 3 hours

#### 7.3.2 Optimize critical paths
- [ ] Profile slow queries
- [ ] Add database indexes
- [ ] Optimize caching
- [ ] Reduce latency
- **Tests**: Performance benchmarks
- **Acceptance**: P95 < 2.5s achieved
- **Effort**: 4 hours

#### 7.3.3 Test resource usage
- [ ] Monitor memory usage
- [ ] Check CPU utilization
- [ ] Verify disk I/O
- [ ] Test connection pools
- **Tests**: Resource monitoring
- **Acceptance**: Fits in 4GB RAM
- **Effort**: 2 hours

## Milestone 8: Observability (Week 8)

### 8.1 Monitoring Setup 🔴

#### 8.1.1 Configure Prometheus
- [ ] Setup Prometheus server
- [ ] Add service discovery
- [ ] Configure retention
- [ ] Add recording rules
- **Tests**: Metric collection tests
- **Acceptance**: Metrics collected and stored
- **Effort**: 3 hours

#### 8.1.2 Instrument services
- [ ] Add Prometheus metrics
- [ ] Track custom metrics
- [ ] Add histogram buckets
- [ ] Export business metrics
- **Tests**: Metric accuracy tests
- **Acceptance**: All services instrumented
- **Effort**: 4 hours

#### 8.1.3 Create Grafana dashboards
- [ ] Design service dashboard
- [ ] Add business metrics
- [ ] Create alert panels
- [ ] Configure variables
- **Tests**: Dashboard functionality
- **Acceptance**: Meaningful visualizations
- **Effort**: 4 hours

### 8.2 Logging & Tracing 🔴

#### 8.2.1 Setup structured logging
- [ ] Configure JSON logging
- [ ] Add correlation IDs
- [ ] Implement log levels
- [ ] Add context injection
- **Tests**: Log format tests
- **Acceptance**: Structured logs with context
- **Effort**: 3 hours

#### 8.2.2 Configure log aggregation
- [ ] Setup Loki
- [ ] Configure log shipping
- [ ] Add log parsing
- [ ] Create queries
- **Tests**: Log query tests
- **Acceptance**: Logs searchable in Loki
- **Effort**: 3 hours

#### 8.2.3 Implement distributed tracing
- [ ] Setup OpenTelemetry
- [ ] Add trace propagation
- [ ] Configure sampling
- [ ] Create trace views
- **Tests**: Trace correlation tests
- **Acceptance**: Request flow visible
- **Effort**: 4 hours

### 8.3 Alerting 🔴

#### 8.3.1 Define alert rules
- [ ] Create SLO-based alerts
- [ ] Add threshold alerts
- [ ] Configure alert routing
- [ ] Set severity levels
- **Tests**: Alert trigger tests
- **Acceptance**: Alerts fire correctly
- **Effort**: 3 hours

#### 8.3.2 Setup notification channels
- [ ] Configure email alerts
- [ ] Add Slack integration
- [ ] Setup PagerDuty (optional)
- [ ] Test alert delivery
- **Tests**: Notification delivery tests
- **Acceptance**: Alerts received promptly
- **Effort**: 2 hours

## Milestone 9: Security & Hardening (Week 9)

### 9.1 Security Implementation 🔴

#### 9.1.1 Add input validation
- [ ] Implement strict schemas
- [ ] Add SQL injection prevention
- [ ] Prevent XSS attacks
- [ ] Add rate limiting
- **Tests**: Security vulnerability tests
- **Acceptance**: Common attacks prevented
- **Effort**: 4 hours

#### 9.1.2 Implement secrets management
- [ ] Setup secret rotation
- [ ] Use environment variables
- [ ] Encrypt sensitive data
- [ ] Add audit logging
- **Tests**: Secret handling tests
- **Acceptance**: No hardcoded secrets
- **Effort**: 3 hours

#### 9.1.3 Configure TLS
- [ ] Setup TLS certificates
- [ ] Configure HTTPS only
- [ ] Add HSTS headers
- [ ] Implement cert renewal
- **Tests**: TLS configuration tests
- **Acceptance**: All traffic encrypted
- **Effort**: 3 hours

### 9.2 Resilience Patterns 🔴

#### 9.2.1 Implement circuit breakers
- [ ] Add py-breaker to services
- [ ] Configure thresholds
- [ ] Add fallback logic
- [ ] Monitor breaker status
- **Tests**: Circuit breaker tests
- **Acceptance**: Services fail gracefully
- **Effort**: 3 hours

#### 9.2.2 Add retry mechanisms
- [ ] Implement exponential backoff
- [ ] Add jitter to retries
- [ ] Configure retry limits
- [ ] Add retry metrics
- **Tests**: Retry behavior tests
- **Acceptance**: Transient failures handled
- **Effort**: 3 hours

#### 9.2.3 Setup graceful degradation
- [ ] Define degradation tiers
- [ ] Implement fallback responses
- [ ] Add feature flags
- [ ] Monitor degradation
- **Tests**: Degradation scenario tests
- **Acceptance**: Service degrades gracefully
- **Effort**: 4 hours

## Milestone 10: Deployment & Operations (Week 9-10)

### 10.1 Deployment Preparation 🔴

#### 10.1.1 Create deployment scripts
- [ ] Write deployment automation
- [ ] Add rollback procedures
- [ ] Configure blue-green deploy
- [ ] Add smoke tests
- **Tests**: Deployment script tests
- **Acceptance**: Automated deployment works
- **Effort**: 4 hours

#### 10.1.2 Setup infrastructure
- [ ] Provision VPS/cloud resources
- [ ] Configure networking
- [ ] Setup domain and DNS
- [ ] Add SSL certificates
- **Tests**: Infrastructure tests
- **Acceptance**: Infrastructure ready
- **Effort**: 4 hours

#### 10.1.3 Configure backups
- [ ] Setup database backups
- [ ] Configure file backups
- [ ] Test restore procedures
- [ ] Add monitoring
- **Tests**: Backup/restore tests
- **Acceptance**: Data recoverable
- **Effort**: 3 hours

### 10.2 Production Deployment 🔴

#### 10.2.1 Deploy to staging
- [ ] Deploy all services
- [ ] Run smoke tests
- [ ] Verify monitoring
- [ ] Test integrations
- **Tests**: Staging validation
- **Acceptance**: Staging environment works
- **Effort**: 3 hours

#### 10.2.2 Performance tuning
- [ ] Optimize database queries
- [ ] Tune cache settings
- [ ] Adjust worker counts
- [ ] Configure rate limits
- **Tests**: Performance benchmarks
- **Acceptance**: Meets SLO targets
- **Effort**: 4 hours

#### 10.2.3 Production deployment
- [ ] Deploy to production
- [ ] Verify all services
- [ ] Monitor metrics
- [ ] Document runbooks
- **Tests**: Production smoke tests
- **Acceptance**: System live and stable
- **Effort**: 4 hours

### 10.3 Documentation 🔴

#### 10.3.1 Write API documentation
- [ ] Document all endpoints
- [ ] Add example requests
- [ ] Include error codes
- [ ] Generate OpenAPI spec
- **Tests**: Documentation accuracy
- **Acceptance**: Complete API docs
- **Effort**: 3 hours

#### 10.3.2 Create operational runbooks
- [ ] Document common issues
- [ ] Add troubleshooting guides
- [ ] Create incident response
- [ ] Include recovery procedures
- **Tests**: Runbook validation
- **Acceptance**: Ops team ready
- **Effort**: 4 hours

#### 10.3.3 User documentation
- [ ] Write user guide
- [ ] Create FAQ
- [ ] Add integration guides
- [ ] Include examples
- **Tests**: Documentation review
- **Acceptance**: Users can self-serve
- **Effort**: 3 hours

## MVP Completion Checklist

### Core Functionality ✅
- [ ] WhatsApp queries working
- [ ] Returns accurate sections
- [ ] 3-line summaries generated
- [ ] Citations included
- [ ] P95 latency < 2.5s

### Data Coverage ✅
- [ ] Labour Act indexed
- [ ] Selected SIs included
- [ ] Cross-references mapped
- [ ] Temporal queries work

### Production Readiness ✅
- [ ] Monitoring active
- [ ] Logs aggregated
- [ ] Alerts configured
- [ ] Backups automated
- [ ] Security hardened

### Documentation ✅
- [ ] API documented
- [ ] Deployment guide
- [ ] Operational runbooks
- [ ] User documentation

### Quality Gates ✅
- [ ] 80% test coverage
- [ ] All tests passing
- [ ] Performance targets met
- [ ] Security scan clean
- [ ] Code review complete

---

## 📊 Summary Statistics

**Total Tasks**: 180+  
**Estimated Effort**: 480-520 hours  
**Team Size**: 2-3 developers recommended  
**Timeline**: 9-10 weeks with dedicated team  

## 🚀 Getting Started

1. Start with Milestone 0 (Foundation)
2. Each task should be a separate PR
3. Maintain test coverage above 80%
4. Deploy to staging after each milestone
5. Get user feedback early and often

## 📝 Notes

- Tasks are ordered by dependency
- Each task includes tests as part of completion
- Effort estimates assume familiarity with tech stack
- Adjust timeline based on team size and experience
- Consider parallel work where dependencies allow

---

**Ready to build? Start with task 0.1.1 and work through systematically!**
