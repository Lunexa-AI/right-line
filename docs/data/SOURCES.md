# RightLine Data Sources (Phase 2)

This document lists the authoritative sources for the Zimbabwe legal RAG MVP, with provenance and usage notes.

## Scope (Phase 2 MVP)
- Labour Act [Chapter 28:01] (latest consolidated version)
- Selected Statutory Instruments (e.g., wages/working hours SIs)
- A small seed set of labour-related case law (ZimLII)

## Provenance & Licensing
- Prefer official or public-domain sources.
- Record for each source: URL, access date, license/terms.
- Respect robots.txt and site terms of use.

## Repository layout for data
- `data/raw/<source>/<filename>` — raw downloads (PDFs/HTML)
- `data/processed/` — normalized/extracted text produced by the ingestion pipeline
- `docs/data/sources.yaml` — manifest of sources to fetch (create from example)

## How to configure downloads
1. Copy the example manifest:
   ```bash
   cp docs/data/sources.yaml.example docs/data/sources.yaml
   ```
2. Fill in the `url` fields for each item (Labour Act, SIs, ZimLII cases).
3. Run the fetcher:
   ```bash
   # ensure venv is active and deps installed
   python3 scripts/fetch_sources.py --config docs/data/sources.yaml --out data/raw --delay 1.0
   ```

## Example entries in sources.yaml
- Labour Act PDF (official consolidated PDF)
- Sectoral Wages Order PDFs (by sector)
- 10 labour-related judgments from ZimLII (PDF or HTML snapshot)

## Notes
- Keep the initial set small and representative for the MVP; expand in Phase 3.
- Do not commit large PDFs directly; prefer git-lfs or store externally.
