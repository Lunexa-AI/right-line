### Task 4: Chunking Strategy (docs.jsonl → chunks.jsonl)

This document provides a comprehensive guide for implementing the chunking strategy for RightLine's RAG system, aligned with `docs/project/INGESTION_AND_CHUNKING.md` section 5. It details how we'll transform normalized document objects from `data/processed/docs.jsonl` into optimally-sized, overlapping chunks ready for embedding.

References: `INGESTION_AND_CHUNKING.md` sections 5.1-5.3, 8.1, and 9.

---

## 4.1 Chunk Schema Definition

Each chunk object will contain the following fields, as specified in `INGESTION_AND_CHUNKING.md` section 3.2:

```json
{
  "chunk_id": "sha256_16(doc_id + section_path + start_char + end_char + text_hash)",
  "doc_id": "parent document ID",
  "chunk_text": "Clean text content (max ~5000 chars)",
  "section_path": "Hierarchical path (e.g., 'Part II > Section 12A' or 'Headnote > Para 3')",
  "start_char": 1234,
  "end_char": 5678,
  "num_tokens": 512,
  "language": "eng",
  "doc_type": "act|judgment|constitution|other",
  "date_context": "2016-12-31",
  "entities": {
    "people": ["Justice Smith", "John Doe"],
    "courts": ["High Court of Zimbabwe"],
    "places": ["Harare"],
    "statute_refs": ["Labour Act [Chapter 28:01]"]
  },
  "source_url": "https://zimlii.org/...",
  "metadata": {
    "title": "Document title",
    "court": "High Court",
    "canonical_citation": "[2025] ZWHHC 123",
    "section": "Section 12A",
    "chunk_index": 3,
    "additional_context": "..."
  }
}
```

Notes:
- `chunk_id`: Stable, deterministic ID ensuring idempotent processing
- `chunk_text`: Clean text with normalized whitespace, quotes, etc.
- `section_path`: Hierarchical location within document
- `start_char`/`end_char`: Character offsets in original document for traceability
- `num_tokens`: Estimated token count (important for OpenAI API)
- `entities`: Extracted entities using regex/heuristics
- `metadata`: Additional context for retrieval filtering and ranking

---

## 4.2 Common Chunking Principles

The following principles will guide our chunking implementation regardless of document type:

### 4.2.1 Target Size and Constraints

- **Target size**: ~512 tokens per chunk (approx. 750-1000 characters)
- **Maximum size**: 5000 characters hard cap (to stay within Milvus varchar limits)
- **Minimum size**: 100 tokens (to ensure meaningful semantic content)
- **Overlap**: 15-20% tokens between consecutive chunks (sliding window)

### 4.2.2 Natural Boundaries

- Prefer breaking at natural boundaries: section/paragraph/sentence breaks
- Only split across these boundaries when necessary to maintain target size
- Never split in the middle of a sentence if possible

### 4.2.3 Context Preservation

- Include hierarchical path information in `section_path`
- For important sections, include short header in `chunk_text` (e.g., "Section 12A: Dismissal")
- Ensure each chunk can stand alone semantically while maintaining context

### 4.2.4 Token Estimation

- Use approximate token counting: ~4 characters per token for English text
- Store actual `num_tokens` estimate for each chunk for monitoring and cost estimation
- Adjust chunk size dynamically based on token estimates

---

## 4.3 Document-Specific Chunking Strategies

### 4.3.1 Legislation Chunking

For acts, statutory instruments, and other legislative documents:

#### Primary Unit: Section

- Each section is the natural atomic unit for legislation
- Process each section in the hierarchical content tree

#### Size-Based Processing

1. **If section text > target size (>512 tokens)**:
   - Split into paragraphs
   - Recompose paragraphs into ~512 token bins with 20% overlap
   - Example: A 1200-token section might become 3 chunks of ~500 tokens each, with 100-token overlap

2. **If section text < target/2 (<256 tokens)**:
   - Consider merging with adjacent section content (in same Part)
   - Preserve distinct `section_path` in metadata
   - Example: Merge short Section 12A (200 tokens) with Section 12B (150 tokens)

#### Section Headers

- Include section number and heading in `metadata.section`
- Optionally prefix the first line of `chunk_text` with "Section 12A: [Heading]" for clarity
- Example: "Section 12A: Dismissal. (1) An employer shall not..."

#### Example Legislation Chunk

```json
{
  "chunk_id": "a1b2c3d4e5f67890",
  "doc_id": "labour_act_2016",
  "chunk_text": "Section 12A: Dismissal. (1) An employer shall not terminate a contract of employment on notice unless— (a) the termination is in terms of an employment code...",
  "section_path": "Part II > Section 12A",
  "start_char": 5240,
  "end_char": 6150,
  "num_tokens": 498,
  "language": "eng",
  "doc_type": "act",
  "date_context": "2016-12-31",
  "entities": {
    "statute_refs": ["Section 12A"]
  },
  "source_url": "https://zimlii.org/zw/legislation/act/1985/16/eng@2016-12-31",
  "metadata": {
    "title": "Labour Act",
    "section": "Section 12A — Dismissal",
    "chunk_index": 0
  }
}
```

### 4.3.2 Judgment Chunking

For court judgments, decisions, and similar case documents:

#### Primary Unit: Paragraphs

- Individual paragraphs are the natural units for judgments
- Special handling for headnote as a distinct section

#### Headnote Processing

- Headnote becomes its own chunk(s)
- If headnote > target size, split with 15% overlap
- Set `section_path` to "Headnote" or "Headnote > Part N"

#### Body Paragraph Processing

1. **Compose sequential paragraphs** into ~512 token chunks with 15-20% overlap
2. **Include paragraph indices** in `section_path` (e.g., `Body > Paras 14-18`)
3. **Store metadata** for filtering and ranking:
   - `court`: Court name for authority-based ranking
   - `neutral_citation`: For reference and citation matching
   - `date_decided`: For recency-based ranking

#### Example Judgment Chunk

```json
{
  "chunk_id": "9f8e7d6c5b4a3210",
  "doc_id": "judgment_2025_zwhhc_304",
  "chunk_text": "The legal principles which underpin the consideration of an application for discharge in terms of s 198(3) of the Code are as follows. The starting point is the section itself, which reads as follows: \"(3) If at the close of the case for the prosecution the court considers that there is no evidence that the accused committed the offence charged in the indictment...",
  "section_path": "Body > Paras 14-16",
  "start_char": 3240,
  "end_char": 4150,
  "num_tokens": 505,
  "language": "eng",
  "doc_type": "judgment",
  "date_context": "2025-05-14",
  "entities": {
    "statute_refs": ["s 198(3) of the Code"]
  },
  "source_url": "https://zimlii.org/zw/judgment/zwhhc/2025/304/eng@2025-05-14",
  "metadata": {
    "title": "Shumba and Others v The State",
    "court": "High Court of Zimbabwe",
    "neutral_citation": "[2025] ZWHHC 304",
    "date_decided": "2025-05-14",
    "chunk_index": 3
  }
}
```

---

## 4.4 Sliding Window Implementation

The sliding window algorithm ensures proper overlap between chunks while respecting natural boundaries:

### 4.4.1 Algorithm Outline

1. **Initialize** with first paragraph/section
2. **Accumulate** paragraphs/text until reaching target size (~512 tokens)
3. **Create chunk** from accumulated text
4. **Slide window back** by 80-85% (creating 15-20% overlap)
5. **Continue** from new position
6. **Repeat** until document is fully processed

### 4.4.2 Overlap Calculation

- For 512-token target with 15% overlap:
  - Overlap = 512 * 0.15 = ~77 tokens
  - Next chunk starts at current_start + (512 - 77) = current_start + 435

### 4.4.3 Boundary Handling

- When sliding window lands mid-paragraph:
  - Option 1: Slide back to nearest sentence boundary
  - Option 2: Include full paragraph in both chunks if paragraph is small
  - Option 3: Split at word boundary if necessary

### 4.4.4 Special Cases

- **Very long paragraphs**: Split at sentence boundaries
- **Lists and enumerations**: Keep items together when possible
- **Tables**: Process as a single unit if possible, otherwise split logically
- **Quoted text**: Keep intact when possible

---

## 4.5 Entity Extraction (MVP-level)

We'll implement lightweight entity extraction using regex patterns and heuristics:

### 4.5.1 Entity Types

- **Dates**: ISO format (YYYY-MM-DD)
  - Pattern: `\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b` or `\b\d{1,2}\s+(?:January|February|...)\s+\d{4}\b`

- **Section references**:
  - Pattern: `\bs(?:ection)?\s*\d+[A-Z]?(?:\s*\(\d+\))?(?:\s*\([a-z]\))?`
  - Examples: "s 12A", "Section 12A", "section 12A(1)(a)"

- **Case citations**:
  - Pattern: `\[\d{4}\]\s+[A-Z]{2,5}\s+\d+` or `\d{4}\s*\(\d+\)\s*[A-Z]{2,5}\s*\d+`
  - Examples: "[2025] ZWHHC 304", "1990 (1) ZLR 172"

- **Party names**:
  - Pattern: `([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+v\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)`
  - Examples: "Shumba and Others v The State"

- **Courts**:
  - Lookup list: "High Court", "Supreme Court", "Constitutional Court", etc.

### 4.5.2 Entity Storage

- Store extracted entities in the `entities` field
- Use for enhanced retrieval and filtering
- Example:
  ```json
  "entities": {
    "dates": ["2025-05-14"],
    "statute_refs": ["Section 12A", "s 198(3)"],
    "case_refs": ["[2025] ZWHHC 304"],
    "courts": ["High Court of Zimbabwe"]
  }
  ```

---

## 4.6 Stable Chunk ID Generation

Chunk IDs must be stable across runs for idempotent processing:

### 4.6.1 ID Components

- `doc_id`: Parent document ID
- `section_path`: Hierarchical location
- `start_char`/`end_char`: Character offsets
- `text_hash`: Hash of the chunk text itself

### 4.6.2 Algorithm

```python
def generate_chunk_id(doc_id, section_path, start_char, end_char, chunk_text):
    """Generate a stable, deterministic chunk ID."""
    components = f"{doc_id}|{section_path}|{start_char}|{end_char}|{hash_text(chunk_text)}"
    return sha256_16(components)

def sha256_16(text):
    """Generate a 16-character SHA256 hash."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

def hash_text(text):
    """Generate a hash of the text content only."""
    # Normalize whitespace before hashing to ensure stability
    normalized = re.sub(r'\s+', ' ', text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
```

---

## 4.7 Data Quality and Cleaning Rules

To ensure high-quality chunks, we'll apply the following cleaning rules:

### 4.7.1 Text Normalization

- Convert all dates to ISO `YYYY-MM-DD` format
- Normalize whitespace, quotes, dashes, and section numbering
- Remove duplicate paragraphs/headers/footers
- Preserve headings as metadata; avoid polluting `chunk_text` with navigation elements

### 4.7.2 Quality Checks

- **Minimum content**: Ensure chunks have sufficient meaningful content
- **Maximum length**: Enforce 5000 character limit
- **Duplicate detection**: Flag near-duplicate chunks
- **Empty sections**: Log anomalies (e.g., empty sections, extremely long sections)

### 4.7.3 Token Estimation

- Use approximate token counting: ~4 characters per token for English text
- For more accurate estimation, use a tokenizer similar to what OpenAI uses
- Log token counts for monitoring and cost estimation

---

## 4.8 Output Format (chunks.jsonl)

The output will be written to `data/processed/chunks.jsonl` with one JSON object per line:

```json
{"chunk_id": "a1b2c3d4e5f67890", "doc_id": "labour_act_2016", "chunk_text": "Section 12A: Dismissal...", ...}
{"chunk_id": "b2c3d4e5f6789012", "doc_id": "labour_act_2016", "chunk_text": "termination of employment...", ...}
```

### 4.8.1 Output Schema Validation

- Ensure all required fields are present
- Validate field types and constraints
- Check for chunk size limits (tokens and characters)

### 4.8.2 Logging and Metrics

- Log number of chunks generated per document
- Track average chunk size (tokens and characters)
- Report overlap statistics
- Flag any anomalies or warnings

---

## 4.9 Implementation Approach

### 4.9.1 High-Level Algorithm

1. **Load documents** from `data/processed/docs.jsonl`
2. **For each document**:
   - Determine document type (legislation or judgment)
   - Apply appropriate chunking strategy
   - Generate chunks with proper overlap
   - Extract entities
   - Create chunk objects with stable IDs
3. **Write chunks** to `data/processed/chunks.jsonl`

### 4.9.2 Pseudocode

```python
def process_documents(input_file, output_file):
    documents = load_jsonl(input_file)
    all_chunks = []
    
    for doc in documents:
        if doc["doc_type"] == "act":
            chunks = chunk_legislation(doc)
        else:  # judgment or other
            chunks = chunk_judgment(doc)
            
        all_chunks.extend(chunks)
        
    write_jsonl(output_file, all_chunks)
    
    print(f"Generated {len(all_chunks)} chunks from {len(documents)} documents")
```

### 4.9.3 Testing Strategy

- Unit tests for chunking algorithms
- Integration tests with sample documents
- Validation of output schema
- Manual review of sample chunks for quality

---

## 4.10 Acceptance Criteria

The chunking implementation will be considered successful when:

1. All documents from `data/processed/docs.jsonl` are processed
2. Chunks follow the specified schema and size constraints
3. Chunks have appropriate overlap
4. Stable chunk IDs are generated
5. Entity extraction is performed
6. Output is written to `data/processed/chunks.jsonl`
7. Logging provides clear metrics on the chunking process

---

This comprehensive chunking strategy ensures that our documents are optimally prepared for embedding and retrieval, balancing semantic coherence with effective vector search. The approach is aligned with state-of-the-art practices in RAG systems while being tailored to the specific needs of legal text processing.
