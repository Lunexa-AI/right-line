-- DEPRECATED: Initialize RightLine PostgreSQL Database
-- This file is deprecated in favor of serverless architecture (Vercel + Milvus + OpenAI)
-- Analytics are now handled by Vercel KV, vector storage by Milvus Cloud
-- Keep this file for reference only

-- Create extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create schema
CREATE SCHEMA IF NOT EXISTS rightline;

-- Set search path
SET search_path TO rightline, public;

-- Create tables (placeholder - will be managed by Alembic migrations)
-- This is just to ensure the database is properly initialized

-- Create a version table for tracking
CREATE TABLE IF NOT EXISTS schema_version (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial version
INSERT INTO schema_version (version) VALUES ('0.0.1-init');

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA rightline TO rightline;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA rightline TO rightline;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA rightline TO rightline;

-- Create indexes for common queries (placeholder)
-- Actual indexes will be created by migrations

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Database initialization completed successfully';
END
$$;
