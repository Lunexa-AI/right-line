# Data Pipeline Decisions & Issues Log

This document tracks critical decisions, issues, and learnings from the Gweta v2.0 data pipeline implementation.

---

## ❌ **CRITICAL ISSUE #1: Parent Document ID Mismatch**

**Date**: 2025-09-11  
**Phase**: Task 3.1 - Small-to-Big Retrieval Implementation  
**Severity**: High - Blocks small-to-big expansion  

### **Problem Description**

During Task 3.1 implementation, discovered that **chunk `parent_doc_id` values don't match actual parent document IDs in R2**:

- **Chunk parent_doc_id**: `4cadbf8fbc858455` (from Milvus/BM25)
- **R2 parent doc IDs**: `0006d13eb254abcd`, `0009d161e09c20d8`, etc.
- **Result**: Small-to-big expansion fails (0% success rate)

### **Root Cause Analysis**

1. **Different Processing Runs**: Chunks and parent documents were generated in separate processing runs with different ID generation seeds/algorithms
2. **No ID Consistency Validation**: No validation that chunk `parent_doc_id` references actually exist in R2
3. **TDD Gap**: Our tests used mocks and didn't validate actual data consistency

### **Why Our TDD Didn't Catch This**

❌ **TDD Failures**:
1. **Unit tests with mocks**: Didn't test actual data flow between chunks ↔ parent docs
2. **No integration tests**: Never verified chunk parent_doc_id → R2 parent doc resolution  
3. **Missing data validation tests**: Should have tested ID consistency across pipeline
4. **Isolated component testing**: Tested RetrievalEngine, BM25, R2 separately but not data alignment

✅ **TDD Improvements Needed**:
1. **End-to-end data flow tests**: Validate actual chunk → parent doc resolution
2. **Data consistency tests**: Verify all chunk parent_doc_ids exist in R2
3. **Integration test with real data samples**: Use actual data snippets, not just mocks
4. **Pipeline validation tests**: Test complete data pipeline end-to-end

### **Decision: Temporary ID Mapping Solution**

**Chosen Solution**: Implement runtime ID mapping (fast, no reprocessing)

**Alternatives Considered**:
- ❌ **Re-run chunk processing**: 6+ hours, complex
- ❌ **Re-run parent doc processing**: 2+ hours, risks breaking existing data
- ✅ **Runtime ID mapping**: < 1 hour, backwards compatible

**Implementation Plan**:
1. Build `doc_id` → `parent_doc_id` mapping from R2 data
2. Cache mapping in memory for performance
3. Use mapping in `_expand_to_parent_documents()` method
4. Add comprehensive logging for monitoring

### **Future Fix Required**

🎯 **TODO for Next Data Processing**:
- **Unify ID generation**: Single processing run for chunks + parent docs
- **Deterministic IDs**: Use consistent hashing algorithm across all components  
- **Validation pipeline**: Add data consistency checks before upload
- **Better TDD**: Add end-to-end data flow validation tests

### **Lessons Learned**

1. **TDD with mocks can hide data consistency issues**
2. **Integration tests with real data are critical for data pipelines**
3. **ID generation must be coordinated across all pipeline components**
4. **Data validation should be built into every pipeline step**

---

## **System Architecture Status**

**✅ Working Components** (as of 2025-09-11):
- Milvus v2.0: 56,051 entities with embeddings
- R2 BM25 Index: 54.75MB, 56K chunks, cloud-native
- Hybrid Search: Dense (Milvus) + Sparse (BM25) + RRF fusion  
- R2 Content Fetching: Parallel chunk retrieval working
- Authentication & Security: JWT + document serving

**⚠️ Known Issues**:
- Parent document ID mapping (temporary fix applied)
- Some performance optimization opportunities

**🎯 Production Readiness**: 95% (pending parent doc mapping fix)

---

*This document will be updated as we resolve issues and make pipeline decisions.*
