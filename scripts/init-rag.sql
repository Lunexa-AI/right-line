-- DEPRECATED: RightLine RAG Database Schema for PostgreSQL
-- This file is deprecated in favor of Milvus Cloud vector store
-- See scripts/init-milvus.py for the new Milvus collection setup
-- Keep this file for reference only

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table - stores source documents
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    document_type VARCHAR(50), -- 'act', 'si', 'case', 'regulation'
    effective_date DATE,
    ingest_date TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(source_url)
);

-- Chunks table - stores document chunks with embeddings
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    doc_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_hash VARCHAR(64), -- SHA256 hash for deduplication
    start_char INTEGER,
    end_char INTEGER,
    embedding vector(384), -- BGE-small-en produces 384-dim vectors
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(doc_id, chunk_index)
);

-- Indexes for efficient search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_chunks_text_fts 
    ON chunks USING GIN (to_tsvector('english', chunk_text));

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id 
    ON chunks(doc_id);

CREATE INDEX IF NOT EXISTS idx_documents_type 
    ON documents(document_type);

CREATE INDEX IF NOT EXISTS idx_documents_effective_date 
    ON documents(effective_date);

-- Query logs table (extends existing queries table)
ALTER TABLE queries ADD COLUMN IF NOT EXISTS 
    retrieved_chunks INTEGER[] DEFAULT '{}';

ALTER TABLE queries ADD COLUMN IF NOT EXISTS 
    response_source VARCHAR(20) DEFAULT 'hardcoded'; -- 'hardcoded' or 'rag'

-- Feedback with chunk relevance
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS 
    relevant_chunk_ids INTEGER[] DEFAULT '{}';

ALTER TABLE feedback ADD COLUMN IF NOT EXISTS 
    irrelevant_chunk_ids INTEGER[] DEFAULT '{}';

-- Create helper functions
CREATE OR REPLACE FUNCTION search_chunks_by_text(
    query_text TEXT,
    limit_count INTEGER DEFAULT 50
)
RETURNS TABLE(
    chunk_id INTEGER,
    chunk_text TEXT,
    doc_title TEXT,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id as chunk_id,
        c.chunk_text,
        d.title as doc_title,
        ts_rank(to_tsvector('english', c.chunk_text), 
                plainto_tsquery('english', query_text)) as rank
    FROM chunks c
    JOIN documents d ON c.doc_id = d.id
    WHERE to_tsvector('english', c.chunk_text) @@ plainto_tsquery('english', query_text)
    ORDER BY rank DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION search_chunks_by_embedding(
    query_embedding vector(384),
    limit_count INTEGER DEFAULT 50
)
RETURNS TABLE(
    chunk_id INTEGER,
    chunk_text TEXT,
    doc_title TEXT,
    similarity REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id as chunk_id,
        c.chunk_text,
        d.title as doc_title,
        1 - (c.embedding <=> query_embedding) as similarity
    FROM chunks c
    JOIN documents d ON c.doc_id = d.id
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL ON documents TO rightline;
GRANT ALL ON chunks TO rightline;
GRANT ALL ON documents_id_seq TO rightline;
GRANT ALL ON chunks_id_seq TO rightline;
