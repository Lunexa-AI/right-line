# Comprehensive Data Pipeline Execution Plan

## Executive Summary

Execute complete data processing pipeline to build comprehensive legal dataset with proper constitutional hierarchy for Gweta Legal AI system.

## Current State Analysis

### R2 Source Documents
- **Acts**: 375 PDFs
- **Ordinances**: 14 PDFs  
- **Statutory Instruments**: 76 PDFs
- **Constitution**: 0 PDFs (needs investigation)
- **TOTAL**: 465 PDFs available

### Current Processing Status
- **Processed**: 15 documents (all classified as "act")
- **Chunks**: ~174 chunks in Milvus (insufficient for comprehensive legal AI)
- **BM25 Index**: Built from limited dataset

## Issues Identified

1. **Constitution Missing**: No Constitution files in expected R2 location
2. **Limited Processing**: Only 15/465 documents processed (3.2%)
3. **Hierarchy Issues**: All documents classified as "act" regardless of type
4. **Insufficient Dataset**: Legal AI needs constitutional hierarchy awareness

## Execution Plan

### Phase 1: Constitution Identification and Classification
**Objective**: Locate Constitution and fix classification system

**Tasks**:
1. Search all R2 locations for Constitution files
2. Check if Constitution is misclassified under acts/
3. Upload Constitution to proper R2 location if missing
4. Modify `parse_docs_v3.py` to detect Constitution by content, not just path
5. Add Constitution-specific metadata extraction

**Success Criteria**:
- Constitution identified and properly classified as `doc_type: "constitution"`
- Constitution available in R2 under `corpus/sources/constitution/`

### Phase 2: Enhanced Document Classification
**Objective**: Improve document type detection for proper hierarchy

**Classification Logic**:
```python
def detect_document_type(filename: str, content: str) -> str:
    """Enhanced document type detection with content analysis."""
    
    # Path-based detection (primary)
    if "/constitution/" in filename.lower():
        return "constitution"
    elif "/acts/" in filename:
        return "act" 
    elif "/ordinances/" in filename:
        return "ordinance"
    elif "/statutory_instruments/" in filename:
        return "si"
    
    # Content-based detection (fallback)
    content_lower = content.lower()
    if "constitution of zimbabwe" in content_lower:
        return "constitution"
    elif "ordinance" in content_lower and "act" not in content_lower:
        return "ordinance"
    elif "statutory instrument" in content_lower:
        return "si"
    else:
        return "act"  # Default fallback
```

**Implementation**:
- Modify `extract_akn_metadata()` in `parse_docs_v3.py`
- Add content-based Constitution detection
- Ensure proper `nature` field mapping

### Phase 3: Complete Document Processing
**Objective**: Process all 465 PDFs with proper classification

**Execution Steps**:
1. **Parse All Documents**:
   ```bash
   python scripts/parse_docs_v3.py --force --verbose
   ```
   - Process all 465 PDFs
   - Apply enhanced classification
   - Upload to `corpus/docs/{doc_type}/{doc_id}.json`

2. **Verify Processing Results**:
   - Check document type distribution
   - Verify Constitution is properly classified
   - Confirm hierarchical metadata

**Expected Output**:
- 465 processed documents in R2
- Proper doc_type distribution: constitution, act, ordinance, si
- Enhanced metadata with constitutional hierarchy

### Phase 4: Comprehensive Chunking
**Objective**: Chunk all documents with hierarchy awareness

**Execution Steps**:
1. **Chunk All Documents**:
   ```bash
   python scripts/chunk_docs.py --force --verbose
   ```
   - Process all parsed documents
   - Generate ~15,000-20,000 chunks (estimate)
   - Preserve document type hierarchy in chunks

2. **Hierarchy-Aware Chunking**:
   - Constitution chunks marked as highest authority
   - Act chunks properly referenced with Chapter numbers
   - SI chunks linked to parent Acts where applicable

**Expected Output**:
- 15,000+ chunks uploaded to `corpus/chunks/{doc_type}/`
- Proper metadata inheritance from parent documents
- Constitutional hierarchy preserved

### Phase 5: Milvus Vector Database Population
**Objective**: Upload all chunks to Milvus with proper schema

**Execution Steps**:
1. **Schema Verification**:
   ```bash
   python scripts/get_milvus_schema.py
   ```
   - Verify Milvus schema supports constitutional hierarchy
   - Confirm doc_type field can handle all types

2. **Comprehensive Upsert**:
   ```bash
   python scripts/milvus_upsert_v2.py --batch-size 100 --force
   ```
   - Upload all chunks with embeddings
   - Apply proper doc_type classification
   - Enable constitutional hierarchy queries

**Expected Output**:
- 15,000+ vectors in `legal_chunks_v3` collection
- Document type distribution visible in Milvus
- Constitutional documents searchable with highest authority

### Phase 6: Enhanced BM25 Index
**Objective**: Build comprehensive BM25 index with all document types

**Execution Steps**:
1. **Build Comprehensive Index**:
   ```bash
   python scripts/build_bm25_index.py --force
   ```
   - Include all document types
   - Apply legal-specific tokenization
   - Upload to R2 for production use

**Expected Output**:
- BM25 index with 15,000+ documents
- Constitutional hierarchy awareness
- Optimized for legal terminology

### Phase 7: System Integration and Testing
**Objective**: Test enhanced system with full dataset

**Testing Steps**:
1. **Constitutional Queries**:
   - Test constitutional rights questions
   - Verify Constitution appears first in results
   - Check constitutional hierarchy enforcement

2. **Statutory Analysis**:
   - Test Act-specific questions
   - Verify proper Chapter references
   - Check cross-references between Constitution and Acts

3. **Comprehensive Coverage**:
   - Test queries spanning multiple document types
   - Verify authority hierarchy in responses
   - Check citation quality and relevance

## Constitutional Hierarchy Implementation

### Document Type Priority (for reranking)
```python
HIERARCHY_WEIGHTS = {
    "constitution": 1.0,    # Highest authority
    "act": 0.8,            # Parliamentary legislation
    "ordinance": 0.7,      # Historical ordinances
    "si": 0.6,             # Statutory instruments
    "case": 0.5            # Case law (when added)
}
```

### Metadata Enhancement
```json
{
  "doc_type": "constitution",
  "authority_level": "supreme", 
  "hierarchy_rank": 1,
  "binding_scope": "all_courts",
  "constitutional_section": "56",
  "rights_category": "fundamental"
}
```

## Timeline and Resources

### Estimated Duration
- **Phase 1**: 2-3 hours (Constitution identification + classification fix)
- **Phase 2**: 1 hour (parse_docs_v3.py modifications)
- **Phase 3**: 8-12 hours (process 465 PDFs via PageIndex API)
- **Phase 4**: 4-6 hours (chunk all documents)
- **Phase 5**: 2-3 hours (Milvus upsert with OpenAI embeddings)
- **Phase 6**: 1-2 hours (BM25 index rebuild)
- **Phase 7**: 2-3 hours (comprehensive testing)

**Total**: 20-30 hours for complete pipeline

### Resource Requirements
- **PageIndex API**: ~465 document processing calls
- **OpenAI Embeddings**: ~15,000 embedding calls (text-embedding-3-large)
- **Milvus Storage**: ~3072 dimensions × 15,000 vectors
- **R2 Storage**: ~500MB additional for processed documents and chunks

## Quality Assurance

### Validation Checkpoints
1. **Post-Parsing**: Verify document type distribution and Constitution classification
2. **Post-Chunking**: Check chunk count and hierarchy preservation  
3. **Post-Milvus**: Verify vector search retrieves constitutional documents first
4. **Post-BM25**: Test keyword search covers all document types
5. **System Integration**: Validate constitutional hierarchy in AI responses

### Success Metrics
- **Coverage**: 465/465 documents processed successfully
- **Hierarchy**: Constitution properly classified and prioritized
- **Quality**: Legal AI responses demonstrate constitutional awareness
- **Performance**: Sub-5 second response times maintained
- **Accuracy**: 95%+ citation accuracy with proper authority hierarchy

## Risk Mitigation

### Potential Issues
1. **Constitution Not Found**: May need manual upload or different search strategy
2. **PageIndex Rate Limits**: May need processing in batches with delays
3. **OpenAI API Limits**: May need to spread embedding generation over time
4. **Milvus Capacity**: Large dataset may require index optimization

### Mitigation Strategies
- **Incremental Processing**: Process in batches to handle rate limits
- **Error Recovery**: Checkpoint progress to resume from failures
- **Quality Gates**: Validate each phase before proceeding
- **Rollback Plan**: Keep current working system during transition

## Implementation Priority

### Phase 1 - Immediate (Constitution Fix)
1. Locate or upload Constitution files
2. Fix parse_docs_v3.py classification logic
3. Test Constitution detection

### Phase 2 - Core Pipeline (All Documents) 
1. Process all 465 PDFs
2. Chunk with hierarchy awareness
3. Upload to Milvus and build BM25 index

### Phase 3 - Advanced Features
1. Test constitutional hierarchy in AI responses
2. Optimize prompting system with full dataset
3. Implement advanced quality gates

This plan will transform Gweta from a limited 15-document system into a comprehensive legal AI with full constitutional hierarchy awareness and access to Zimbabwe's complete legal corpus.
