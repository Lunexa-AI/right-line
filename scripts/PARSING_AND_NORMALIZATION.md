### Task 3: Parsing & Normalization (Documents → docs.jsonl)

This guide specifies exactly how we will parse raw ZimLII HTML into normalized document objects and emit `data/processed/docs.jsonl`, fully aligned with `docs/project/INGESTION_AND_CHUNKING.md`.

References: `INGESTION_AND_CHUNKING.md` sections 2–4 and 8.1–8.3.

---

## 3.1 Normalized Document Schema

Document object fields (one JSON object per document):
- doc_id (string): Stable ID. sha256_16(source_url + expression_uri_or_date + title)
- doc_type (string enum): act | si | constitution | judgment | regulation | other
- title (string): Document title (e.g., “Labour Act” or case title)
- source_url (string): Original ZimLII URL
- language (string): ISO code (e.g., "eng")
- jurisdiction (string): "ZW"
- version_effective_date (string|nullable): ISO YYYY-MM-DD for legislation expressions
- canonical_citation (string|nullable): Neutral/statute citation (judgments or acts)
- created_at (string): ISO timestamp when ingested
- updated_at (string): ISO timestamp last processed
- extra (object): Doc-type specific details
  - Legislation: chapter, act_number, expression_uri, effective_start, effective_end, part_map, section_ids
  - Judgment: court, case_number, neutral_citation, date_decided, judges[], parties{...}, headnote (raw), references[]
- content_tree (object): Hierarchical structure for later chunking
  - For acts: parts/chapters/sections with headings, anchor ids, and ordered paragraphs
  - For judgments: headnote and body paragraphs with ordering

Notes:
- Dates: Always ISO (YYYY-MM-DD) when available.
- Keep raw headnote text in `extra.headnote`; cleaned text goes into `content_tree`.

---

## 3.2 HTML Boilerplate Removal Plan

Global removal (both types):
- Drop <script>, <style>, <nav>, <footer>, social/share blocks, banners, cookie notices
- Remove site headers/menus, breadcrumbs, search bars
- Strip inline styles, tracking attributes

Containers to keep (heuristics):
- Prefer the main content container that holds the legal text. Typical candidates on ZimLII pages:
  - div with article/document content (e.g., role="main" or id/class containing "content", "document", "article")
  - For legislation, the sectioned body typically under a central content div
  - For judgments, the decision body container that includes header metadata + paragraphs

Normalization steps:
- Convert HTML to text preserving paragraph boundaries
- Normalize whitespace, Unicode quotes/dashes; collapse multiple spaces
- Preserve headings/anchors as metadata (not inline noise)
- Remove repeated headers/footers if present within content blocks

Acceptance:
- Identified selectors/landmarks per sample files (legislation/judgment)
- Cleaned text contains only the legal content (no menus/scripts)

---

## 3.3 Section/Paragraph Extraction Plan

Legislation (acts/SIs):
1) Extract doc-level metadata:
   - title, chapter, act_number
   - FRBR/AKN expression URI and effective date
   - language, jurisdiction
2) Build hierarchy:
   - Detect Parts/Chapters/Sections by headings and anchors (e.g., Section 12A, anchors per section)
   - For each section: capture heading, anchor id, and ordered paragraphs
3) Store into `content_tree`:
   - parts[] → chapters[] → sections[] → paragraphs[]
   - Record section identifiers and maintain `section_ids` in `extra`

Judgments:
1) Extract header metadata:
   - case title, court, case number, neutral citation, date decided, judges, counsel (if present)
2) Identify headnote/summary block (if present) and store raw text in `extra.headnote` and structured paragraphs in `content_tree`
3) Body paragraphs:
   - Capture ordered paragraphs; record paragraph indices
4) References block and inline citations:
   - Store as `extra.references[]` when available

Acceptance:
- Example documents show correctly identified sections/paragraphs with stable ordering

---

## 3.4 Stable ID Definition

- doc_id = sha256_16(source_url + expression_uri_or_date + title)
  - expression_uri_or_date is FRBR expression URI if available; else the effective date (acts) or date decided (judgments); else empty string
- Deterministic: Same input → same ID across runs

Example (illustrative):
- source_url = "https://zimlii.org/zw/legislation/act/2016/labour-act"
- expression_date = "2016-12-31"
- title = "Labour Act"
- doc_id = sha256_16("https://zim.../labour-act2016-12-31Labour Act") → e.g., "a1b2c3d4e5f67890"

---

## 3.5 Output Plan (docs.jsonl)

File: `data/processed/docs.jsonl`
- One JSON per line (no trailing commas), UTF-8

Sample (Legislation):
```json
{
  "doc_id": "a1b2c3d4e5f67890",
  "doc_type": "act",
  "title": "Labour Act",
  "source_url": "https://zimlii.org/...",
  "language": "eng",
  "jurisdiction": "ZW",
  "version_effective_date": "2016-12-31",
  "canonical_citation": null,
  "created_at": "2025-08-20T18:10:00Z",
  "updated_at": "2025-08-20T18:10:00Z",
  "extra": {
    "chapter": "28:01",
    "act_number": "[if available]",
    "expression_uri": "akn/zw/act/2016-12-31/...",
    "effective_start": "2016-12-31",
    "effective_end": null,
    "section_ids": ["s-12A", "s-13", "s-14"],
    "part_map": {
      "Part II": ["s-12A", "s-13"],
      "Part III": ["s-14"]
    }
  },
  "content_tree": {
    "parts": [
      {
        "title": "Part II",
        "chapters": [],
        "sections": [
          {
            "id": "s-12A",
            "heading": "Section 12A — Dismissal",
            "anchor": "#section-12A",
            "paragraphs": ["Para text 1", "Para text 2", "..."]
          }
        ]
      }
    ]
  }
}
```

Sample (Judgment):
```json
{
  "doc_id": "9f8e7d6c5b4a3210",
  "doc_type": "judgment",
  "title": "X v Y [2020] ZWHC 123",
  "source_url": "https://zimlii.org/...",
  "language": "eng",
  "jurisdiction": "ZW",
  "version_effective_date": null,
  "canonical_citation": "[2020] ZWHC 123",
  "created_at": "2025-08-20T18:10:00Z",
  "updated_at": "2025-08-20T18:10:00Z",
  "extra": {
    "court": "High Court of Zimbabwe",
    "case_number": "HC 123/20",
    "neutral_citation": "[2020] ZWHC 123",
    "date_decided": "2020-06-10",
    "judges": ["Justice A", "Justice B"],
    "parties": {"applicant": "X", "respondent": "Y"},
    "headnote": "[raw headnote text if present]",
    "references": ["Labour Act", "Case Z v W"]
  },
  "content_tree": {
    "headnote": ["Headnote para 1", "Headnote para 2"],
    "body": ["Para 1 text", "Para 2 text", "..."]
  }
}
```

Validation & Acceptance:
- docs.jsonl exists and lines validate as JSON
- Required fields present; dates ISO-formatted when available
- `content_tree` contains ordered sections/paragraphs ready for chunking

---

## Non-Goals (Task 3)
- No embeddings or Milvus writes here
- No chunking yet (handled in Task 4)
- No API wiring here (offline preprocessing only)


