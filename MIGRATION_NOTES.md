# Migration to Vercel + Milvus + OpenAI

This document outlines the changes needed to migrate from the VPS + PostgreSQL architecture to Vercel + Milvus + OpenAI serverless architecture.

## Directory Structure Changes

### Current Structure (VPS-based)
```
right-line/
├── services/api/          # FastAPI application
├── docker-compose.mvp.yml # Docker setup
├── requirements.txt       # Python dependencies
└── ...
```

### New Structure (Vercel-based)
```
right-line/
├── api/                   # Vercel serverless functions (move from services/api/)
│   ├── main.py           # Main FastAPI app with Mangum adapter
│   ├── retrieval.py      # Milvus search functions
│   ├── composer.py       # OpenAI completion functions
│   └── ...
├── web/                   # Static web files (move from services/api/static/)
│   ├── index.html        # Web UI
│   └── ...
├── scripts/              # Ingestion scripts (unchanged)
├── vercel.json           # Vercel configuration
├── requirements.txt      # Updated dependencies
└── ...
```

## Required Changes

### 1. Move FastAPI App to Vercel Functions
- [ ] Create `api/` directory
- [ ] Move `services/api/main.py` to `api/main.py`
- [ ] Add Mangum adapter to `api/main.py` for Vercel compatibility
- [ ] Update imports and paths

### 2. Move Static Files
- [ ] Create `web/` directory  
- [ ] Move `services/api/static/*` to `web/`
- [ ] Update paths in vercel.json

### 3. Update Settings
- [ ] Update `libs/common/settings.py` for new environment variables
- [ ] Add OpenAI and Milvus configuration
- [ ] Remove PostgreSQL/Redis settings

### 4. Create New Components
- [ ] Create `api/retrieval.py` for Milvus search
- [ ] Create `api/composer.py` for OpenAI completion
- [ ] Create `scripts/init-milvus.py` for collection setup

### 5. Update Analytics
- [ ] Replace SQLite analytics with Vercel KV storage
- [ ] Update analytics endpoints

## Deprecated Files

The following files are deprecated but kept for reference:
- `docker-compose.mvp.yml` - Use Vercel deployment instead
- `scripts/init-rag.sql` - Use Milvus instead of PostgreSQL
- VPS deployment scripts - Use Vercel CLI instead

## Migration Steps

1. **Phase 1**: Update documentation (✅ Complete)
2. **Phase 2**: Restructure code files
3. **Phase 3**: Test local development with `vercel dev`
4. **Phase 4**: Deploy to Vercel production
5. **Phase 5**: Set up Milvus and OpenAI integrations

## Cost Comparison

### Old Architecture (VPS)
- VPS: $5-10/month
- Total: $5-10/month

### New Architecture (Serverless)  
- Vercel: Free tier, then $20/month Pro
- Milvus Cloud: Free tier (1GB), then $0.10/million queries
- OpenAI: $0.50/1M embedding tokens + $1.50/1M GPT-3.5 tokens
- Estimated total: $10-30/month depending on usage

## Benefits of Migration

1. **Zero Server Management**: No VPS maintenance, automatic scaling
2. **Global Distribution**: Vercel's global CDN for fast responses
3. **Better AI Integration**: Direct OpenAI API integration
4. **Managed Vector Store**: Milvus Cloud handles indexing and scaling
5. **Developer Experience**: `vercel dev` for local development
