# Entity Extraction and Normalization

This document details the entity extraction and normalization process implemented in `scripts/enrich_chunks.py` as part of Task 5 (Enrichment) from the Ingestion and Chunking Tasklist.

## 1. Entity Types and Patterns

The script extracts and normalizes the following entity types:

### 1.1 Dates

Extracts dates in various formats and normalizes them to ISO format (YYYY-MM-DD):

| Format | Example | Normalized |
|--------|---------|------------|
| DD/MM/YYYY | 21/05/2025 | 2025-05-21 |
| DD-MM-YYYY | 21-05-2025 | 2025-05-21 |
| DD Month YYYY | 21 May 2025 | 2025-05-21 |
| Month DD, YYYY | May 21, 2025 | 2025-05-21 |
| YYYY-MM-DD | 2025-05-21 | 2025-05-21 (unchanged) |

### 1.2 Statute References

Extracts and standardizes references to legislation:

| Format | Example | Normalized |
|--------|---------|------------|
| s 12A | s 12A | Section 12A |
| s. 12A | s. 12A | Section 12A |
| s.12A | s.12A | Section 12A |
| section 12A | section 12A | Section 12A |
| Labour Act [Chapter 28:01] | Labour Act [Chapter 28:01] | Labour Act [Chapter 28:01] |
| Labour Act | Labour Act | Labour Act |

### 1.3 Case Citations

Extracts and standardizes case citations:

| Format | Example | Normalized |
|--------|---------|------------|
| [YYYY] COURT NNN | [2025] ZWHHC 304 | [2025] ZWHHC 304 |
| YYYY (N) COURT NNN | 1998 (2) ZLR 377 | 1998 (2) ZLR 377 |
| S v Name COURT NNN/YY | S v Mulauzi HB 159/16 | S v Mulauzi HB 159/16 |

### 1.4 Court Names

Extracts and standardizes court names:

| Format | Example | Normalized |
|--------|---------|------------|
| High Court | High Court | High Court of Zimbabwe |
| Supreme Court | Supreme Court | Supreme Court of Zimbabwe |
| Constitutional Court | Constitutional Court | Constitutional Court of Zimbabwe |
| Magistrates Court | Magistrates Court | Magistrates Court of Zimbabwe |
| Labour Court | Labour Court | Labour Court of Zimbabwe |

### 1.5 Judge Names

Extracts judge names:

| Format | Example | Normalized |
|--------|---------|------------|
| SURNAME J | MUTEVEDZI J | MUTEVEDZI J |
| SURNAME JA | MATHONSI JA | MATHONSI JA |
| Justice SURNAME | Justice Mutevedzi | Justice Mutevedzi |

### 1.6 Party Names

Extracts party names from case names:

| Format | Example | Normalized |
|--------|---------|------------|
| X v Y | Shumba v The State | {"applicant": "Shumba", "respondent": "The State"} |

## 2. Enrichment Process

The enrichment process performs the following steps:

1. **Extract and normalize entities** from chunk text using regex patterns
2. **Merge with existing entities** if present in the chunk
3. **Extract date context** from dates if available
4. **Add court information** to metadata if available

## 3. Test Strings

The following test strings demonstrate the entity extraction capabilities:

### 3.1 Date Extraction

```
The judgment was delivered on 21 May 2025.
The act came into effect on 2016-12-31.
The hearing took place on January 15, 2025.
```

### 3.2 Statute References

```
According to s 12A of the Labour Act [Chapter 28:01], the employer must...
Section 156(1)(a) of the Criminal Law (Codification and Reform) Act [Chapter 9:23] states...
```

### 3.3 Case Citations

```
In [2025] ZWHHC 304, the court ruled...
The precedent in 1998 (2) ZLR 377 (HC) established that...
S v Mulauzi HB 159/16 is relevant to this case.
```

### 3.4 Court Names and Judges

```
The High Court of Zimbabwe, per MUTEVEDZI J, held that...
Justice Mathonsi, sitting in the Supreme Court, ruled that...
```

### 3.5 Party Names

```
In Shumba and Others v The State, the applicants argued...
```

## 4. Output Format

Entities are stored in the `entities` field of each chunk:

```json
{
  "chunk_id": "a1b2c3d4e5f67890",
  "chunk_text": "...",
  "entities": {
    "dates": ["2025-05-21", "2016-12-31"],
    "statute_refs": ["Section 12A", "Labour Act [Chapter 28:01]"],
    "case_refs": ["[2025] ZWHHC 304", "1998 (2) ZLR 377"],
    "courts": ["High Court of Zimbabwe"],
    "judges": ["MUTEVEDZI J"],
    "parties": [{"applicant": "Shumba", "respondent": "The State"}]
  },
  "date_context": "2025-05-21",
  "metadata": {
    "court": "High Court of Zimbabwe"
  }
}
```
