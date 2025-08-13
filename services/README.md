# RightLine Services

This directory contains the microservices that power RightLine.

## Services

### api/
FastAPI gateway that orchestrates all requests and provides the REST API interface.

### retrieval/
Hybrid search engine combining BM25, vector search, and cross-encoder reranking.

### ingestion/
Document processing pipeline for scraping, OCR, and section extraction.

### summarizer/
Multi-tier summarization service with local LLM and fallback options.

## Development

Each service can be developed and tested independently. See individual service READMEs for details.
