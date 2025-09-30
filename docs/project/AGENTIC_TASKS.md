# Agentic Architecture: Implementation Task Breakdown

**Document Purpose**: Break down all 5 enhancements from `AGENTIC_ARCHITECTURE_ENHANCEMENT.md` into actionable tasks.

**Reference**: For implementation code, see `AGENTIC_ARCHITECTURE_ENHANCEMENT.md`

**Timeline**: 7 weeks | **Tasks**: 74 | **Effort**: ~200 hours (1 FTE)

**NEW**: Memory systems added (ARCH-031 to ARCH-046) - Short-term conversation context + Long-term user patterns

---

## Task Format

**Each task includes**:
- Task ID, Priority, Time Estimate
- Dependencies
- Objective
- Files to modify
- Reference to code in enhancement doc
- Acceptance criteria
- Testing requirements

---

# PHASE 1: CRITICAL FIXES (Week 1)
**10 tasks | 12 hours**

## Enhancement 1: Cross-Encoder Reranking

### ARCH-001: Replace Score Sorting with Cross-Encoder ✅ COMPLETE
- **Priority**: P0 | **Time**: 2-3h | **Dependencies**: None
- **Objective**: Fix line 613 in `query_orchestrator.py` - use actual BGE cross-encoder instead of score sorting
- **Files**: `api/orchestrators/query_orchestrator.py` (_rerank_node method)
- **Code**: Enhancement doc → Enhancement 1 → lines 196-350
- **Acceptance**:
  - ✅ BGE cross-encoder called (not score sort)
  - ✅ Quality threshold applied (score >= 0.3)
  - ✅ Logs show "bge_crossencoder" method
  - ✅ Graceful fallback on error
- **Testing**: Verify cross-encoder is used, not score sorting
- **Status**: ✅ COMPLETE - 12/12 tests passing

### ARCH-002: Add Diversity Filtering ✅ COMPLETE
- **Priority**: P0 | **Time**: 1h | **Dependencies**: ARCH-001
- **Objective**: Prevent >40% of results from single document
- **Files**: `api/orchestrators/query_orchestrator.py` (add _apply_diversity_filter)
- **Code**: Enhancement doc → Enhancement 1 → Diversity section
- **Acceptance**:
  - ✅ Max 40% from one parent doc
  - ✅ Two-pass filtering (diversity + fill)
  - ✅ Logs show diversity metrics
- **Testing**: Test with all results from same doc
- **Status**: ✅ COMPLETE - Diversity filter working

### ARCH-003: Create Reranking Tests ✅ COMPLETE
- **Priority**: P0 | **Time**: 1.5h | **Dependencies**: ARCH-001, ARCH-002
- **Objective**: Comprehensive test suite for reranking
- **Files**: `tests/api/orchestrators/test_reranking.py`
- **Acceptance**:
  - ✅ Tests: cross-encoder usage, quality threshold, diversity, fallback
  - ✅ Coverage >90%
  - ✅ All tests pass (12/12)
- **Testing**: `pytest -v -k rerank`
- **Status**: ✅ COMPLETE - 12 tests created and passing

### ARCH-004: Add LangSmith Metrics ✅ COMPLETE
- **Priority**: P0 | **Time**: 30m | **Dependencies**: ARCH-001
- **Objective**: Add detailed reranking metrics for monitoring
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Acceptance**:
  - ✅ Metrics in LangSmith
  - ✅ Before/after scores tracked
  - ✅ Diversity metrics included
- **Testing**: Check LangSmith dashboard
- **Status**: ✅ COMPLETE - Comprehensive metrics added

### ARCH-005: Deploy to Staging ✅ COMPLETE
- **Priority**: P0 | **Time**: 1h | **Dependencies**: ARCH-001-004
- **Objective**: Deploy reranking fix to staging
- **Acceptance**:
  - ✅ Tests pass locally
  - ✅ PR created and approved
  - ✅ Deployed to staging
  - ✅ Smoke tests pass
  - ✅ No errors in logs (1h monitoring)
- **Testing**: Staging smoke tests
- **Status**: ✅ COMPLETE - Deployed and tested on staging

### ARCH-006: Create Quality Evaluation Script ✅ COMPLETE
- **Priority**: P0 | **Time**: 2h | **Dependencies**: ARCH-005
- **Objective**: Measure retrieval quality improvement
- **Files**: `tests/evaluation/measure_reranking_quality.py` (new), `golden_queries.json` (new)
- **Acceptance**:
  - ✅ Golden dataset (15 diverse queries created)
  - ✅ Evaluation script runs successfully
  - ✅ Script supports baseline comparison
  - ✅ Metrics: Precision@K, doc type distribution
- **Testing**: Run evaluation script
- **Status**: ✅ COMPLETE - Script ready, golden dataset created

### ARCH-007: Validate Quality on Staging ✅ COMPLETE
- **Priority**: P0 | **Time**: 4h | **Dependencies**: ARCH-006
- **Objective**: Confirm 20-40% quality improvement
- **Acceptance**:
  - ✅ Precision@5 improved ≥15%
  - ✅ Recall@10 improved ≥10%
  - ✅ Latency acceptable (+200-500ms)
  - ✅ Stakeholder approval
- **Testing**: Monitor 24-48h
- **Status**: ✅ COMPLETE - Quality improvements validated on staging

### ARCH-008: Production Deployment ✅ COMPLETE
- **Priority**: P0 | **Time**: 2h | **Dependencies**: ARCH-007
- **Objective**: Deploy to production
- **Acceptance**:
  - ✅ Deployed successfully
  - ✅ Release tagged
  - ✅ Gradual rollout (10%→100%)
  - ✅ Monitoring dashboard created
  - ✅ Alerts configured
- **Testing**: Monitor 24h
- **Status**: ✅ COMPLETE - Deployed to production

### ARCH-009: Adaptive Retrieval Top-K ✅ COMPLETE
- **Priority**: P1 | **Time**: 1.5h | **Dependencies**: ARCH-001
- **Objective**: Dynamic retrieval params based on complexity
- **Files**: `api/orchestrators/query_orchestrator.py`, `api/schemas/agent_state.py`
- **Code**: Enhancement doc → Adaptive parameters
- **Acceptance**:
  - ✅ Simple: 15→5, Moderate: 25→8, Complex: 40→12, Expert: 50→15
  - ✅ Params calculated in intent classifier
  - ✅ Params used in retrieval and selection nodes
  - ✅ Params logged for monitoring
- **Testing**: Test each complexity level
- **Status**: ✅ COMPLETE - Adaptive parameters implemented in 3 nodes

### ARCH-010: Adaptive Parameters Tests ✅ COMPLETE
- **Priority**: P1 | **Time**: 1h | **Dependencies**: ARCH-009
- **Objective**: Test adaptive parameters
- **Files**: `tests/api/orchestrators/test_adaptive_parameters.py` (new)
- **Acceptance**:
  - ✅ All complexity tests pass (10/10)
  - ✅ Fallback test passes
  - ✅ End-to-end flow tested
- **Testing**: `pytest -v -k adaptive`
- **Status**: ✅ COMPLETE - 10/10 tests passing

---

# PHASE 2: PERFORMANCE (Week 2-3)
**20 tasks | 30 hours**

## Enhancement 4: Multi-Level Caching

### ARCH-011: Set Up Redis Infrastructure ✅ COMPLETE
- **Priority**: P1 | **Time**: 2h | **Dependencies**: None
- **Objective**: Set up Redis for caching
- **Files**: `libs/caching/redis_client.py` (new), `configs/example.env`
- **Tasks**:
  - ✅ Installed redis[hiredis] dependency
  - ✅ Installed fakeredis for testing
  - ✅ Created Redis client with connection pooling
  - ✅ Added REDIS_URL to environment config
  - ✅ Implemented graceful error handling
- **Acceptance**:
  - ✅ Redis client implemented
  - ✅ Connection successful (with fakeredis)
  - ✅ All 7 tests passing
  - ✅ Graceful degradation if Redis unavailable
- **Testing**: `redis-cli ping` or fakeredis
- **Status**: ✅ COMPLETE - 7/7 tests passing, production-grade client

### ARCH-012: Create Cache Module Structure ✅ COMPLETE
- **Priority**: P1 | **Time**: 30m | **Dependencies**: ARCH-011
- **Objective**: Set up caching module
- **Files**: `libs/caching/__init__.py` (new), `libs/caching/redis_client.py` (new)
- **Acceptance**:
  - ✅ Module structure created (`libs/caching/`)
  - ✅ Files importable
  - ✅ Redis client working
- **Testing**: Import test
- **Status**: ✅ COMPLETE - Module structure ready

### ARCH-013: Implement SemanticCache Core ✅ COMPLETE
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-012
- **Objective**: Core cache class with connection management
- **Files**: `libs/caching/semantic_cache.py` (new, 121 lines)
- **Code**: Enhancement doc → Enhancement 4 → SemanticCache class
- **Tasks**:
  - ✅ Created SemanticCache class
  - ✅ Implemented connect/disconnect methods
  - ✅ Implemented exact cache key generation
  - ✅ Implemented stats tracking (CacheStats dataclass)
  - ✅ Implemented basic get_cached_response (exact match only)
  - ✅ Implemented cache_response method
  - ✅ Added graceful error handling
- **Acceptance**:
  - ✅ Class instantiates successfully
  - ✅ Connection works (with fakeredis)
  - ✅ Error handling works
  - ✅ All 8 tests passing
  - ✅ 50% code coverage
- **Testing**: Connection cycle test
- **Status**: ✅ COMPLETE - 8/8 tests passing, core functionality working

### ARCH-014: Implement Exact Match Caching (Level 1) ✅ COMPLETE
- **Priority**: P1 | **Time**: 1.5h | **Dependencies**: ARCH-013
- **Objective**: Hash-based exact match cache
- **Files**: `libs/caching/semantic_cache.py`, `tests/libs/caching/test_exact_match_cache.py` (new)
- **Tasks**:
  - ✅ Implemented _get_exact_cache_key() with MD5 hashing
  - ✅ Query normalization (case-insensitive, whitespace handling)
  - ✅ Get/set with TTL
  - ✅ Hit count tracking in metadata
  - ✅ Stats tracking (exact_hits, misses, hit_rate)
  - ✅ User type separation
  - ✅ Metadata stripping (internal fields)
  - ✅ Concurrent operations support
- **Acceptance**:
  - ✅ Exact match works (<10ms)
  - ✅ Query normalization works (case + whitespace)
  - ✅ TTL expires correctly
  - ✅ Stats tracked accurately
  - ✅ All 14 tests passing
  - ✅ 73% code coverage
- **Testing**: Exact match hit/miss tests
- **Status**: ✅ COMPLETE - 14/14 tests passing, production-ready

### ARCH-015: Implement Semantic Similarity (Level 2) ✅ COMPLETE
- **Priority**: P1 | **Time**: 3h | **Dependencies**: ARCH-014
- **Objective**: Embedding-based similarity search
- **Files**: `libs/caching/semantic_cache.py`, `tests/libs/caching/test_semantic_similarity.py` (new)
- **Code**: Enhancement doc → Semantic similarity section
- **Tasks**:
  - ✅ Implemented _cosine_similarity() with numpy
  - ✅ Implemented _find_similar_cached_query()
  - ✅ Integrated embedding generation in cache_response
  - ✅ Implemented semantic index management (_add_to_semantic_index)
  - ✅ Computed cosine similarity for all cached queries
  - ✅ Find best match above threshold (0.95)
  - ✅ Track semantic hits in stats
  - ✅ Embedding caching (get_embedding_cache, cache_embedding)
  - ✅ Graceful degradation when embeddings unavailable
- **Acceptance**:
  - ✅ Finds semantically similar queries
  - ✅ Similarity threshold enforced (0.95)
  - ✅ Returns None if below threshold
  - ✅ Stats track semantic hits separately
  - ✅ All 9 tests passing
  - ✅ 54% code coverage
- **Testing**: Similar query tests
- **Status**: ✅ COMPLETE - 9/9 tests passing, semantic similarity working!

### ARCH-016: Implement Cache Storage
- **Priority**: P1 | **Time**: 1.5h | **Dependencies**: ARCH-015
- **Objective**: Store responses with embeddings
- **Files**: `libs/caching/semantic_cache.py`
- **Tasks**:
  - Implement cache_response()
  - Store with TTL
  - Store metadata with embedding
  - Add to semantic index
- **Acceptance**:
  - ☐ Responses stored
  - ☐ Embeddings stored
  - ☐ Metadata correct
  - ☐ Added to index
- **Testing**: Storage/retrieval test

### ARCH-017: Implement Intent Caching
- **Priority**: P1 | **Time**: 45m | **Dependencies**: ARCH-013
- **Objective**: Cache intent classifications
- **Files**: `libs/caching/semantic_cache.py`
- **Tasks**:
  - Implement get_intent_cache()
  - Implement cache_intent()
  - TTL = 2 hours
- **Acceptance**:
  - ☐ Intent cached/retrieved
  - ☐ TTL = 2h
- **Testing**: Intent cache test

### ARCH-018: Implement Embedding Caching
- **Priority**: P1 | **Time**: 45m | **Dependencies**: ARCH-013
- **Objective**: Cache query embeddings
- **Files**: `libs/caching/semantic_cache.py`
- **Tasks**:
  - Implement get_embedding_cache()
  - Implement cache_embedding()
  - TTL = 1 hour
- **Acceptance**:
  - ☐ Embeddings cached/retrieved
  - ☐ TTL = 1h
- **Testing**: Embedding cache test

### ARCH-019: Add Cache Statistics
- **Priority**: P1 | **Time**: 1h | **Dependencies**: ARCH-014, ARCH-015
- **Objective**: Track cache performance
- **Files**: `libs/caching/semantic_cache.py`
- **Tasks**:
  - Update CacheStats
  - Track all operations
  - Implement get_stats()
  - Add clear_cache()
- **Acceptance**:
  - ☐ Stats accurate
  - ☐ Hit rate calculated
  - ☐ Clear cache works
- **Testing**: Stats accuracy test

### ARCH-020: Create Cache Tests
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-014-018
- **Objective**: Comprehensive cache test suite
- **Files**: `tests/libs/caching/test_semantic_cache.py` (new)
- **Tasks**:
  - Test exact match
  - Test semantic similarity
  - Test cache miss
  - Test TTL
  - Test intent cache
  - Test embedding cache
  - Test stats
  - Test error handling
- **Acceptance**:
  - ☐ All cache levels tested
  - ☐ Coverage >90%
  - ☐ All tests pass
- **Testing**: `pytest tests/libs/caching/ -v`

### ARCH-021: Integrate Cache in Intent Classifier
- **Priority**: P1 | **Time**: 1h | **Dependencies**: ARCH-017
- **Objective**: Add intent caching to classifier
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Tasks**:
  - Check intent cache first
  - Cache after classification
  - Handle errors gracefully
- **Acceptance**:
  - ☐ Cache checked first
  - ☐ Intent cached
  - ☐ Logs show hits/misses
- **Testing**: Intent cache hit/miss test

### ARCH-022: Integrate Cache in Orchestrator
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-020, ARCH-021
- **Objective**: Main cache integration in run_query
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Code**: Enhancement doc → Cache integration section
- **Tasks**:
  - Initialize cache in __init__
  - Check cache at start of run_query
  - Return cached on hit
  - Cache response after pipeline
  - Determine TTL by complexity
- **Acceptance**:
  - ☐ Cache checked first
  - ☐ Cache hit <100ms
  - ☐ Responses cached
  - ☐ TTL varies
  - ☐ Logs show performance
- **Testing**: Cache hit/miss path tests

### ARCH-023: Deploy Caching to Staging
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-022
- **Objective**: Deploy caching to staging
- **Tasks**:
  - Set up Redis on staging
  - Deploy code
  - Run smoke tests
  - Monitor hit rate
- **Acceptance**:
  - ☐ Redis on staging
  - ☐ Cache working
  - ☐ Hits observable
  - ☐ Latency reduced
- **Testing**: Same query twice (second cached)

### ARCH-024: Monitor Cache Performance
- **Priority**: P1 | **Time**: 4h | **Dependencies**: ARCH-023
- **Objective**: Monitor and optimize
- **Tasks**:
  - Monitor 24-48h
  - Track hit rate
  - Optimize TTL
  - Document performance
- **Acceptance**:
  - ☐ Hit rate 40-60%
  - ☐ Latency improvement quantified
  - ☐ Performance documented
- **Testing**: 24-48h monitoring

## Enhancement 2: Speculative Execution

### ARCH-025: Refactor Graph for Parallel Execution
- **Priority**: P1 | **Time**: 2h | **Dependencies**: None
- **Objective**: Enable parallel node execution
- **Files**: `api/orchestrators/query_orchestrator.py` (_build_graph)
- **Code**: Enhancement doc → Parallel execution section
- **Tasks**:
  - Identify parallel opportunities
  - Refactor graph edges
  - Add synchronization
- **Acceptance**:
  - ☐ Graph supports parallel
  - ☐ No state conflicts
  - ☐ Compiles successfully
- **Testing**: Test graph execution

### ARCH-026: Implement Speculative Prefetching
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-025
- **Objective**: Prefetch top 15 parent docs
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Code**: Enhancement doc → Speculative prefetch section
- **Tasks**:
  - Create _parent_prefetch_speculative node
  - Get top 15 results
  - Batch fetch from R2
  - Store in state cache
- **Acceptance**:
  - ☐ Prefetches 15 docs
  - ☐ Uses batch fetching
  - ☐ Completes <150ms
  - ☐ Cached in state
- **Testing**: Test prefetch timing

### ARCH-027: Implement Fast Parent Selection
- **Priority**: P1 | **Time**: 1h | **Dependencies**: ARCH-026
- **Objective**: Use cached docs (no R2 fetch)
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Tasks**:
  - Create _parent_final_select node
  - Get docs from cache
  - Build context (no R2!)
  - Handle cache misses
- **Acceptance**:
  - ☐ Uses cache
  - ☐ No R2 fetches
  - ☐ Completes <20ms
- **Testing**: Test cache hit/miss

### ARCH-028: Implement Parallel Quality Gates
- **Priority**: P1 | **Time**: 1.5h | **Dependencies**: ARCH-025
- **Objective**: Run attribution & coherence in parallel
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Tasks**:
  - Split quality gate into 2 nodes
  - Create merge node
  - Update graph for parallel
- **Acceptance**:
  - ☐ Run in parallel
  - ☐ Results merged
  - ☐ Time reduced ~50%
- **Testing**: Test parallel execution

### ARCH-029: Update Graph Edges
- **Priority**: P1 | **Time**: 1h | **Dependencies**: ARCH-026-028
- **Objective**: Wire new nodes
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Tasks**:
  - Add speculative edges
  - Add parallel edges
  - Test compilation
- **Acceptance**:
  - ☐ Graph compiles
  - ☐ Edges correct
  - ☐ No deadlocks
- **Testing**: Full graph test

### ARCH-030: Measure Performance
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-029
- **Objective**: Quantify improvements
- **Files**: `tests/evaluation/measure_parallel_performance.py` (new)
- **Tasks**:
  - Measure baseline
  - Measure new latency
  - Calculate improvements
  - Document results
- **Acceptance**:
  - ☐ 15-25% improvement achieved
  - ☐ Per-node timing documented
- **Testing**: Run on staging

---

# PHASE 2B: MEMORY SYSTEMS (Week 3-4)
**15 tasks | 25 hours**

## Enhancement 6: Short-Term and Long-Term Memory

### ARCH-031: Design Memory Architecture
- **Priority**: P1 | **Time**: 2h | **Dependencies**: None
- **Objective**: Design comprehensive memory system architecture
- **Files**: `docs/architecture/memory_system.md` (new)
- **Tasks**:
  - Design short-term memory structure (conversation context)
  - Design long-term memory structure (user patterns)
  - Define memory storage strategy (Redis + Firestore)
  - Define memory retrieval strategy
  - Define memory update triggers
  - Plan token budget for memory context
- **Acceptance**:
  - ☐ Architecture document created
  - ☐ Short-term structure defined
  - ☐ Long-term structure defined
  - ☐ Storage strategy clear
- **Testing**: Architecture review with team

### ARCH-032: Implement Short-Term Memory Manager
- **Priority**: P1 | **Time**: 3h | **Dependencies**: ARCH-031
- **Objective**: Manage conversation context within session
- **Files**: `libs/memory/short_term.py` (new)
- **Tasks**:
  - Create ShortTermMemory class
  - Store last N messages (default 10)
  - Store in Redis with session_id key
  - Implement sliding window (FIFO)
  - Add message compression for token efficiency
  - Implement get_context() for recent messages
  - Add TTL (session expiry after 24h)
  - Track conversation topics
- **Acceptance**:
  - ☐ Stores last N messages
  - ☐ Sliding window works
  - ☐ Context retrievable
  - ☐ TTL expires correctly
  - ☐ Token-efficient
- **Testing**: Test message storage and retrieval

### ARCH-033: Implement Long-Term Memory Manager
- **Priority**: P1 | **Time**: 3h | **Dependencies**: ARCH-031
- **Objective**: Track user patterns and preferences
- **Files**: `libs/memory/long_term.py` (new)
- **Tasks**:
  - Create LongTermMemory class
  - Track frequently asked topics
  - Track legal areas of interest
  - Store user preferences (complexity, verbosity)
  - Implement query pattern analysis
  - Store in Firestore (persistent)
  - Build user interest profile
  - Update incrementally after each query
- **Acceptance**:
  - ☐ Tracks topics over time
  - ☐ Identifies patterns
  - ☐ Stores in Firestore
  - ☐ Updates incrementally
  - ☐ User profile buildable
- **Testing**: Test pattern tracking

### ARCH-034: Create Memory Integration Point
- **Priority**: P1 | **Time**: 1h | **Dependencies**: ARCH-032, ARCH-033
- **Objective**: Central memory coordinator
- **Files**: `libs/memory/__init__.py`, `libs/memory/coordinator.py` (new)
- **Tasks**:
  - Create MemoryCoordinator class
  - Integrate short-term and long-term managers
  - Implement unified get_context() method
  - Balance token budget across memory types
  - Prioritize recent over historical
  - Add memory retrieval logging
- **Acceptance**:
  - ☐ Coordinates both memory types
  - ☐ Token budget managed
  - ☐ Context prioritized correctly
  - ☐ Logs memory usage
- **Testing**: Test memory prioritization

### ARCH-035: Integrate Short-Term Memory in Query Rewriter
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-032, ARCH-034
- **Objective**: Use conversation context for query rewriting
- **Files**: `api/orchestrators/query_orchestrator.py` (_rewrite_expand_node)
- **Tasks**:
  - Fetch short-term memory at query rewrite
  - Extract recent queries and responses
  - Resolve pronouns (it, this, that → specific terms)
  - Resolve context references ("as mentioned before")
  - Enhance query with conversation context
  - Handle follow-up questions
  - Log context usage
- **Acceptance**:
  - ☐ Conversation context retrieved
  - ☐ Pronouns resolved correctly
  - ☐ Follow-ups understood
  - ☐ Context enhances query
  - ☐ Logs context usage
- **Testing**: Test follow-up queries

### ARCH-036: Integrate Long-Term Memory in Intent Classifier
- **Priority**: P1 | **Time**: 1.5h | **Dependencies**: ARCH-033, ARCH-034
- **Objective**: Use user patterns for better intent classification
- **Files**: `api/orchestrators/query_orchestrator.py` (_route_intent_node)
- **Tasks**:
  - Fetch long-term memory at classification
  - Use user's typical complexity level
  - Use user's typical legal areas
  - Adjust user_type based on history
  - Personalize intent confidence
  - Log memory influence
- **Acceptance**:
  - ☐ User patterns retrieved
  - ☐ Classification personalized
  - ☐ Confidence adjusted
  - ☐ Logs memory usage
- **Testing**: Test with user history

### ARCH-037: Implement Memory Update After Query
- **Priority**: P1 | **Time**: 1.5h | **Dependencies**: ARCH-032, ARCH-033
- **Objective**: Update memories after each query
- **Files**: `api/orchestrators/query_orchestrator.py` (run_query method)
- **Tasks**:
  - Add memory update node or post-hook
  - Update short-term with current exchange
  - Update long-term with query patterns
  - Extract legal topics from query
  - Update user interest profile
  - Handle update failures gracefully
  - Log memory updates
- **Acceptance**:
  - ☐ Short-term updated
  - ☐ Long-term updated
  - ☐ Topics extracted
  - ☐ Profile updated
  - ☐ Errors handled
- **Testing**: Test memory persistence

### ARCH-038: Add Memory Context to State
- **Priority**: P1 | **Time**: 1h | **Dependencies**: ARCH-034
- **Objective**: Include memory in AgentState
- **Files**: `api/schemas/agent_state.py`
- **Tasks**:
  - Add short_term_context field
  - Add long_term_profile field
  - Add memory_tokens_used field
  - Add conversation_topics field
  - Validate memory doesn't exceed token budget
  - Document memory fields
- **Acceptance**:
  - ☐ Memory fields added
  - ☐ Token budget enforced
  - ☐ Fields documented
  - ☐ Pydantic validation works
- **Testing**: Test state validation

### ARCH-039: Implement Session History Retrieval
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-032
- **Objective**: Fetch recent session messages efficiently
- **Files**: `libs/firestore/session.py` (enhance existing)
- **Tasks**:
  - Enhance get_session_history() for performance
  - Add caching for recent fetches
  - Implement efficient pagination
  - Add message summarization for old messages
  - Return in format suitable for context
  - Handle large sessions gracefully
- **Acceptance**:
  - ☐ Efficient retrieval
  - ☐ Caching works
  - ☐ Summarization for old messages
  - ☐ Token-efficient
- **Testing**: Test with large sessions

### ARCH-040: Create User Profile Builder
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-033
- **Objective**: Build comprehensive user profiles over time
- **Files**: `libs/memory/profile_builder.py` (new)
- **Tasks**:
  - Create ProfileBuilder class
  - Extract legal areas from query history
  - Identify user expertise level (citizen vs professional)
  - Track preferred response style
  - Track typical query complexity
  - Build interest graph
  - Update incrementally
  - Store in Firestore user document
- **Acceptance**:
  - ☐ Profiles built from history
  - ☐ Expertise level identified
  - ☐ Interests tracked
  - ☐ Updates incrementally
  - ☐ Stored in Firestore
- **Testing**: Test profile building

### ARCH-041: Implement Memory-Aware Synthesis
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-035, ARCH-036
- **Objective**: Use memory to personalize synthesis
- **Files**: `api/orchestrators/query_orchestrator.py` (_synthesize_stream_node)
- **Tasks**:
  - Include conversation context in synthesis
  - Reference previous queries if relevant
  - Adapt response style to user profile
  - Use preferred complexity level
  - Mention related previous questions
  - Log memory usage in synthesis
- **Acceptance**:
  - ☐ Context included in synthesis
  - ☐ References previous queries
  - ☐ Style adapted
  - ☐ Logs memory usage
- **Testing**: Test personalization

### ARCH-042: Create Memory Compression Strategy
- **Priority**: P1 | **Time**: 1.5h | **Dependencies**: ARCH-032
- **Objective**: Compress old messages to save tokens
- **Files**: `libs/memory/compression.py` (new)
- **Tasks**:
  - Create message summarizer
  - Compress messages older than 5 exchanges
  - Preserve key legal terms
  - Preserve citations
  - Use GPT-4o-mini for compression
  - Target 50-70% token reduction
- **Acceptance**:
  - ☐ Old messages compressed
  - ☐ Key info preserved
  - ☐ 50-70% token savings
  - ☐ Quality maintained
- **Testing**: Test compression quality

### ARCH-043: Implement Follow-Up Question Handler
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-035
- **Objective**: Handle follow-up questions elegantly
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Tasks**:
  - Detect follow-up patterns ("what about", "and if")
  - Fetch relevant previous response
  - Merge previous context with new query
  - Maintain conversation coherence
  - Reference previous answers explicitly
  - Log follow-up detection
- **Acceptance**:
  - ☐ Follow-ups detected
  - ☐ Previous context used
  - ☐ Coherent conversation
  - ☐ References previous answers
- **Testing**: Test follow-up chains

### ARCH-044: Create Memory Tests
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-032, ARCH-033
- **Objective**: Comprehensive memory testing
- **Files**: `tests/libs/memory/test_short_term.py`, `tests/libs/memory/test_long_term.py` (new)
- **Tasks**:
  - Test short-term storage and retrieval
  - Test sliding window
  - Test long-term pattern tracking
  - Test profile building
  - Test memory updates
  - Test token budget enforcement
  - Test compression
- **Acceptance**:
  - ☐ All memory functions tested
  - ☐ Coverage >85%
  - ☐ All tests pass
- **Testing**: `pytest tests/libs/memory/ -v`

### ARCH-045: Deploy Memory to Staging
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-044
- **Objective**: Deploy memory features to staging
- **Tasks**:
  - Deploy code to staging
  - Test conversation continuity
  - Test follow-up questions
  - Test profile building
  - Monitor token usage
  - Check Firestore writes
  - Validate memory performance
- **Acceptance**:
  - ☐ Deployed successfully
  - ☐ Conversation continuity works
  - ☐ Follow-ups handled
  - ☐ Profiles updating
  - ☐ Performance acceptable
- **Testing**: Multi-turn conversations on staging

### ARCH-046: Monitor and Optimize Memory
- **Priority**: P1 | **Time**: 4h | **Dependencies**: ARCH-045
- **Objective**: Monitor memory effectiveness
- **Tasks**:
  - Monitor token usage from memory
  - Track follow-up resolution accuracy
  - Measure profile building quality
  - Optimize compression ratios
  - Adjust memory window sizes
  - Document memory performance
- **Acceptance**:
  - ☐ Token usage optimized
  - ☐ Follow-ups resolved >90%
  - ☐ Profiles accurate
  - ☐ Performance documented
- **Testing**: Monitor 48h on staging

---

# PHASE 3: REASONING (Week 5-6)
**18 tasks | 35 hours**

## Enhancement 5: Advanced Intent Classification

### ARCH-047: Enhance Heuristic Classifier
- **Priority**: P1 | **Time**: 2h | **Dependencies**: None
- **Objective**: Better pattern matching & complexity assessment
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Code**: Enhancement doc → Advanced intent section
- **Tasks**:
  - Add user type detection
  - Add intent patterns
  - Add complexity assessment
  - Calculate retrieval params
- **Acceptance**:
  - ☐ User type detected
  - ☐ Complexity accurate
  - ☐ Params calculated
- **Testing**: Test each intent/complexity

### ARCH-048: Update Intent Classifier
- **Priority**: P1 | **Time**: 1h | **Dependencies**: ARCH-047, ARCH-021
- **Objective**: Use enhanced heuristics with cache
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Tasks**:
  - Check cache
  - Use heuristics
  - Fallback to LLM
  - Cache result
- **Acceptance**:
  - ☐ Heuristics used 80%+
  - ☐ LLM fallback works
  - ☐ Params set in state
- **Testing**: Test all paths

## Enhancement 3: Self-Correction

### ARCH-049: Add Quality Decision Logic
- **Priority**: P1 | **Time**: 1.5h | **Dependencies**: None
- **Objective**: Decide when to refine/retrieve
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Code**: Enhancement doc → Refinement decision
- **Tasks**:
  - Create _decide_refinement_strategy
  - Check quality & iteration count
  - Analyze issues
  - Return decision
- **Acceptance**:
  - ☐ Returns correct decision
  - ☐ Respects max iterations (2)
  - ☐ Logs reasoning
- **Testing**: Test each decision type

### ARCH-050: Implement Self-Critic Node
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-049
- **Objective**: Generate refinement instructions
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Code**: Enhancement doc → Self-critic section
- **Tasks**:
  - Create _self_critic_node
  - Build criticism prompt
  - Use GPT-4o-mini
  - Parse instructions
  - Increment iteration
- **Acceptance**:
  - ☐ Generates instructions
  - ☐ JSON parsing works
  - ☐ Iteration incremented
- **Testing**: Test with various issues

### ARCH-051: Implement Refined Synthesis
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-050
- **Objective**: Re-synthesize with improvements
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Code**: Enhancement doc → Refined synthesis
- **Tasks**:
  - Create _refined_synthesis_node
  - Use refinement instructions
  - Generate improved answer
  - Mark as refinement
- **Acceptance**:
  - ☐ Uses instructions
  - ☐ Produces improved synthesis
  - ☐ Metadata shows refinement
- **Testing**: Verify quality improvement

### ARCH-052: Implement Iterative Retrieval
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-049
- **Objective**: Retrieve more when insufficient
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Code**: Enhancement doc → Iterative retrieval
- **Tasks**:
  - Create _iterative_retrieval_node
  - Analyze gaps
  - Generate gap query
  - Retrieve additional
  - Deduplicate & merge
- **Acceptance**:
  - ☐ Identifies gaps
  - ☐ Retrieves additional
  - ☐ Deduplicates
  - ☐ Merges correctly
- **Testing**: Test with insufficient sources

### ARCH-053: Create Gap Query Generator
- **Priority**: P1 | **Time**: 1h | **Dependencies**: ARCH-052
- **Objective**: Generate targeted gap queries
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Tasks**:
  - Create _generate_gap_filling_query
  - Analyze quality issues
  - Build targeted query
- **Acceptance**:
  - ☐ Generates targeted query
  - ☐ Focuses on gaps
- **Testing**: Test with various gaps

### ARCH-054: Update Graph for Self-Correction
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-050-052
- **Objective**: Add self-correction loops
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Tasks**:
  - Add new nodes to graph
  - Add conditional edges
  - Add loop-back edges
  - Test compilation
- **Acceptance**:
  - ☐ All nodes added
  - ☐ Routing works
  - ☐ Graph compiles
- **Testing**: Test routing

### ARCH-055: Add Iteration Limit
- **Priority**: P1 | **Time**: 30m | **Dependencies**: ARCH-054
- **Objective**: Max 2 iterations
- **Files**: `api/orchestrators/query_orchestrator.py`, `api/schemas/agent_state.py`
- **Tasks**:
  - Track iteration count
  - Force pass at max
  - Add warning if needed
- **Acceptance**:
  - ☐ Max 2 enforced
  - ☐ Logs iteration count
- **Testing**: Test max iterations

### ARCH-056: Create Self-Correction Tests
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-054-055
- **Objective**: Test self-correction end-to-end
- **Files**: `tests/api/orchestrators/test_self_correction.py` (new)
- **Tasks**:
  - Test refinement path
  - Test iterative retrieval
  - Test max iterations
  - Test quality improvement
- **Acceptance**:
  - ☐ All paths tested
  - ☐ Max iteration enforced
  - ☐ All tests pass
- **Testing**: `pytest test_self_correction.py -v`

### ARCH-057: Deploy Self-Correction to Staging
- **Priority**: P1 | **Time**: 2h | **Dependencies**: ARCH-056
- **Objective**: Deploy to staging
- **Tasks**:
  - Deploy code
  - Test with refinement queries
  - Monitor trigger rates
  - Check improvements
- **Acceptance**:
  - ☐ Deployed successfully
  - ☐ Triggers appropriately
  - ☐ Quality improves
- **Testing**: Test borderline queries

### ARCH-058: Measure Self-Correction Effectiveness
- **Priority**: P1 | **Time**: 4h | **Dependencies**: ARCH-057
- **Objective**: Measure quality improvements
- **Files**: `tests/evaluation/measure_self_correction.py` (new)
- **Tasks**:
  - Create evaluation script
  - Measure before/after
  - Calculate improvements
  - Document trigger rate
- **Acceptance**:
  - ☐ Triggers ~15% of complex
  - ☐ Quality improves
  - ☐ Results documented
- **Testing**: Monitor 24-48h

### ARCH-059-064: Integration & Testing
- Additional tasks for integration testing, performance regression, load testing, documentation, monitoring, runbooks

---

# PHASE 4: HARDENING (Week 7)
**10 tasks | 20 hours**

### ARCH-065: Implement Graceful Degradation
- **Priority**: P2 | **Time**: 3h | **Dependencies**: All previous
- **Objective**: Fallbacks for all nodes
- **Files**: `api/orchestrators/query_orchestrator.py`
- **Tasks**:
  - Review each node
  - Add try-catch
  - Implement fallbacks
  - Test failures
- **Acceptance**:
  - ☐ All nodes have error handling
  - ☐ Fallbacks tested
  - ☐ Pipeline continues
- **Testing**: Test each failure

### ARCH-066: Add Circuit Breakers
- **Priority**: P2 | **Time**: 2h | **Dependencies**: ARCH-065
- **Objective**: Prevent cascade failures
- **Files**: `libs/reliability/circuit_breaker.py` (new)
- **Tasks**:
  - Create CircuitBreaker class
  - Add for Redis, R2, Milvus, OpenAI
  - Configure thresholds
- **Acceptance**:
  - ☐ Circuit breakers implemented
  - ☐ Opens on failures
  - ☐ Cooldown works
- **Testing**: Test opening/closing

### ARCH-067: Create Load Testing
- **Priority**: P2 | **Time**: 3h | **Dependencies**: All previous
- **Objective**: Test with 1000 concurrent users
- **Files**: `tests/load/load_test.py` (new)
- **Tasks**:
  - Create load test script
  - Configure 1000 users
  - Measure latencies
  - Identify bottlenecks
- **Acceptance**:
  - ☐ 1000 users tested
  - ☐ Metrics collected
  - ☐ Bottlenecks identified
- **Testing**: Run on staging

### ARCH-068: Set Up Monitoring Dashboard
- **Priority**: P2 | **Time**: 2h | **Dependencies**: All previous
- **Objective**: Production monitoring
- **Tasks**:
  - Create dashboard
  - Add key metrics
  - Real-time updates
- **Acceptance**:
  - ☐ Dashboard created
  - ☐ All metrics displayed
  - ☐ Real-time updates
- **Testing**: Verify on staging

### ARCH-069: Configure Alerting
- **Priority**: P2 | **Time**: 1.5h | **Dependencies**: ARCH-068
- **Objective**: Alerts for critical issues
- **Tasks**:
  - Configure alerts
  - Set thresholds
  - Test notifications
- **Acceptance**:
  - ☐ Alerts configured
  - ☐ Thresholds appropriate
  - ☐ Notifications work
- **Testing**: Trigger each alert

### ARCH-070: Create Runbooks
- **Priority**: P2 | **Time**: 3h | **Dependencies**: All previous
- **Objective**: Operational procedures
- **Files**: `docs/operations/runbooks.md` (new)
- **Tasks**:
  - Create runbooks for common issues
  - Document troubleshooting
  - Document rollback
- **Acceptance**:
  - ☐ Runbooks created
  - ☐ Steps clear
  - ☐ Team trained
- **Testing**: Review with ops team

### ARCH-071: Update Architecture Docs
- **Priority**: P2 | **Time**: 2h | **Dependencies**: All previous
- **Objective**: Document all enhancements
- **Files**: `docs/architecture/`
- **Tasks**:
  - Update diagrams
  - Document new components
  - Update API docs
- **Acceptance**:
  - ☐ All components documented
  - ☐ Diagrams updated
- **Testing**: Review with team

### ARCH-072: Production Deployment
- **Priority**: P0 | **Time**: 3h | **Dependencies**: All previous
- **Objective**: Deploy all enhancements
- **Tasks**:
  - Deploy to production
  - Gradual rollout
  - Monitor closely
  - Verify all features
- **Acceptance**:
  - ☐ Deployed successfully
  - ☐ All features enabled
  - ☐ Metrics healthy
  - ☐ No critical alerts
- **Testing**: Production smoke tests

### ARCH-073: Post-Deployment Validation
- **Priority**: P0 | **Time**: 8h | **Dependencies**: ARCH-072
- **Objective**: Validate production performance
- **Tasks**:
  - Run production tests
  - Measure all metrics
  - Collect feedback
  - Document performance
- **Acceptance**:
  - ☐ Cache hit rate 40-60%
  - ☐ Quality improved 20-40%
  - ☐ Latency targets met
  - ☐ User feedback positive
- **Testing**: Monitor 72h

### ARCH-074: Final Retrospective
- **Priority**: P3 | **Time**: 2h | **Dependencies**: ARCH-073
- **Objective**: Document results & lessons
- **Files**: `docs/project/ENHANCEMENT_RESULTS.md` (new)
- **Tasks**:
  - Conduct retrospective
  - Document lessons learned
  - Document final metrics
  - Share results
- **Acceptance**:
  - ☐ Retrospective done
  - ☐ Results documented
  - ☐ Success story created
- **Testing**: N/A

---

## Summary

**74 tasks** across **4 phases** over **7 weeks** (~200 hours)

**Memory Enhancement Added**: 16 new tasks for short-term and long-term memory (ARCH-031 to ARCH-046)

**Phase 1** (Week 1): 10 tasks - Fix reranking, adaptive params
**Phase 2** (Week 2-3): 20 tasks - Caching, speculative execution
**Phase 2B** (Week 3-4): 16 tasks - Memory systems (short-term & long-term)
**Phase 3** (Week 5-6): 18 tasks - Self-correction, advanced intent
**Phase 4** (Week 7): 10 tasks - Production hardening

**Key Milestones**:
- Week 1: +20-40% quality
- Week 3: 50-80% latency reduction
- Week 5: Self-correction working
- Week 6: Production ready

**For implementation code**, see: `AGENTIC_ARCHITECTURE_ENHANCEMENT.md`

**Ready to start?** Begin with **ARCH-001**!
