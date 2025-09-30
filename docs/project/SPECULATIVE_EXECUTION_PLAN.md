# Speculative Execution Implementation Plan

## Current Status

**Starting**: ARCH-025 to ARCH-030 (6 tasks)  
**Goal**: Reduce latency by 15-25% through parallelization

---

## Current Graph Analysis

### **Current Sequential Flow**:
```
01_intent_classifier (100ms)
    ↓
02_query_rewriter (150ms)
    ↓
03_retrieval_parallel (800ms) ← Already parallel internally (BM25 ∥ Milvus)
    ↓
04_merge_results (10ms)
    ↓
04b_relevance_filter (100ms)
    ↓
05_rerank (400ms) ← Now using cross-encoder!
    ↓
06_select_topk (5ms)
    ↓
07_parent_expansion (500ms) ← Can optimize!
    ↓
08_synthesis (2000ms)
    ↓
08b_quality_gate (300ms) ← Can parallelize!
    ↓
09_answer_composer (20ms)

Total: ~4.4 seconds
```

---

## Optimization Opportunities

### **1. Parallel Quality Gates** (ARCH-028)
**Current**: Attribution → Coherence (sequential, 300ms total)  
**Optimized**: Attribution ∥ Coherence (parallel, ~150ms)  
**Savings**: 150ms (3.4% reduction)

**Easy Win**: Low complexity, high value

### **2. Speculative Parent Prefetching** (ARCH-026-027)
**Current**: Wait for rerank, then fetch top 5-12 parents (500ms)  
**Optimized**: Fetch top 15 speculatively during rerank, select 5-12 from cache (<20ms)  
**Savings**: 480ms (10.9% reduction)

**High Impact**: Significant latency reduction

### **3. Overlap Synthesis and Quality Gates** (Advanced)
**Current**: Synthesis (2000ms) → Quality gates (300ms)  
**Optimized**: Start quality gates during synthesis streaming  
**Savings**: ~100-200ms (partial overlap)

**Complex**: Requires careful state management

---

## Implementation Priority

### **ARCH-025**: Document current graph, identify parallel opportunities ✅ (This doc)

### **ARCH-026**: Speculative parent prefetch (Highest ROI)
- Fetch top 15 parents speculatively
- Cache in state
- **Impact**: 480ms savings

### **ARCH-027**: Fast parent selection from cache
- Use prefetched parents
- Near-zero latency
- **Impact**: Enables ARCH-026

### **ARCH-028**: Parallel quality gates  
- Split into 2 nodes
- Run in parallel
- Merge results
- **Impact**: 150ms savings

### **ARCH-029**: Update graph edges for new structure

### **ARCH-030**: Measure and validate improvements

**Total Expected Savings**: ~600ms (13.6% reduction)

---

## Recommendation

Given time constraints and complexity:

**Option A**: Focus on high-impact tasks
- ARCH-026-027: Speculative prefetch (480ms savings)
- ARCH-028: Parallel quality gates (150ms savings)
- **Total**: ~600ms (13.6% reduction), ~6 hours work

**Option B**: Document and skip for now
- Document opportunities
- Mark as future enhancement
- Move to Phase 2B (memory) or Phase 3 (reasoning loops)
- **Benefit**: Focus on other high-value features

**Option C**: Simplified parallel quality gates only
- ARCH-028 only (parallel quality gates)
- **Total**: 150ms savings, ~2 hours work
- Quick win, lower complexity

---

## My Recommendation

**Option C**: Just do parallel quality gates (ARCH-028)
- **Why**: Quick win, clear benefit, low complexity
- **Time**: 2 hours
- **Impact**: 150ms savings
- **Risk**: Low

**Then**: Move to Phase 2B (Memory) or Phase 3 (Reasoning loops) - higher business value

**Defer**: Speculative prefetching to later optimization phase

---

**What would you prefer?**
1. Full speculative execution (A - 6 hours)
2. Skip to next phase (B - document only)
3. Just parallel quality gates (C - 2 hours) ← Recommended

Let me know and I'll implement accordingly! 🚀
