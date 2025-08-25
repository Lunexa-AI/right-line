# Gweta: Remaining Tasks to MVP

> **🎯 Final sprint to MVP completion**  
> New positioning: Gweta Web is an enterprise research workbench (less‑ink, evidence‑first). Gweta WhatsApp is a free chatbot for citizens (“smart lawyer friend”). We have end‑to‑end RAG; finish UI polish, deployment, and channel separation.

## 📊 Current State Analysis (What's ✅ Done)

### ✅ **Core RAG Pipeline (100% Complete)**
- **Parsing & Normalization**: AKN-aware parser for Labour Act + judgments (`scripts/parse_docs.py`)
- **Chunking & Enrichment**: Smart chunking with entity extraction (`scripts/chunk_docs.py`)
- **Embeddings**: OpenAI text-embedding-3-small integration (`scripts/generate_embeddings.py`)
- **Vector Store**: Milvus Cloud collection with 472 chunks indexed and searchable
- **Retrieval**: Vector search with confidence scoring (`api/retrieval.py`)
- **Composition**: OpenAI GPT-4o-mini with extractive fallback (`api/composer.py`)
- **API Integration**: RAG-enabled `/api/v1/query` endpoint working end-to-end
- **Web Interface**: Modern UI with progressive disclosure, working with RAG responses

### ✅ **Infrastructure & Architecture (95% Complete)**
- **Serverless Architecture**: FastAPI + Mangum adapter for Vercel
- **Environment Configuration**: Settings with proper validation
- **Analytics System**: Vercel KV-based analytics with feedback endpoints
- **CORS & Security**: Proper CORS configuration for web interface
- **Documentation**: Comprehensive architecture and deployment guides

### ✅ **Data & Content (100% Complete)**
- **Legal Documents**: Labour Act and judgments crawled and processed
- **Vector Database**: 472 chunks with embeddings in Milvus Cloud
- **Search Quality**: Verified working with relevant results

---

## 🚀 **Remaining Tasks to MVP (Final Sprint)**

### **Priority 1: WhatsApp Channel (Citizens) (4 hours)**

#### Task 1.1: Update WhatsApp to use RAG system
- **Current State**: WhatsApp integration exists but uses hardcoded responses
- **Required**: Update `api/whatsapp.py` to use RAG system instead of `get_hardcoded_response`
- **Files to modify**: 
  - `api/whatsapp.py` (line 343: replace `get_hardcoded_response` with RAG calls)
  - Test WhatsApp formatting with new response structure
- **Acceptance**: WhatsApp messages use RAG responses with proper formatting
- **Effort**: 2 hours

#### Task 1.2: WhatsApp Business API setup & testing
- **Required**: Configure WhatsApp Business API credentials for testing
- **Environment variables needed**:
  ```bash
  RIGHTLINE_WHATSAPP_VERIFY_TOKEN=your_verify_token
  RIGHTLINE_WHATSAPP_ACCESS_TOKEN=your_access_token  
  RIGHTLINE_WHATSAPP_PHONE_NUMBER_ID=your_phone_id
  ```
- **Acceptance**: Can send/receive messages via WhatsApp webhook
- **Effort**: 2 hours

### **Priority 2: Vercel Deployment (3 hours)**

#### Task 2.1: Environment variables configuration
- **Required**: Set up Vercel environment variables
- **Variables to configure**:
  ```bash
  # Core settings
  RIGHTLINE_SECRET_KEY=production-secret-key-32chars-minimum
  RIGHTLINE_APP_ENV=production
  RIGHTLINE_CORS_ORIGINS=https://your-domain.vercel.app
  
  # OpenAI
  OPENAI_API_KEY=sk-your-production-key
  OPENAI_EMBEDDING_MODEL=text-embedding-3-small
  OPENAI_MODEL=gpt-4o-mini
  OPENAI_MAX_TOKENS=300
  
  # Milvus Cloud
  MILVUS_ENDPOINT=https://your-cluster.aws-eu-central-1.cloud.zilliz.com
  MILVUS_TOKEN=your-production-token
  MILVUS_COLLECTION_NAME=legal_chunks
  
  # Vercel KV (optional for analytics)
  KV_REST_API_URL=https://your-kv-store.upstash.io
  KV_REST_API_TOKEN=your-kv-token
  ```
- **Acceptance**: All environment variables configured in Vercel dashboard
- **Effort**: 1 hour

#### Task 2.2: Deploy to Vercel
- **Required**: Deploy the application to Vercel
- **Commands**:
  ```bash
  vercel login
  vercel --prod
  ```
- **Acceptance**: Application accessible via Vercel URL, all endpoints working
- **Effort**: 1 hour

#### Task 2.3: Verify production deployment
- **Required**: Test all functionality in production
- **Tests**:
  - Web interface loads and works
  - `/api/v1/query` returns RAG responses
  - WhatsApp webhook receives and responds to messages
  - Analytics endpoints work
- **Acceptance**: All core functionality verified in production
- **Effort**: 1 hour

### **Priority 3: Enterprise Web UI (2 hours)**
#### Task 3.1: Apply less‑ink workspace (no suggestions)
- Remove suggestion chips from UI; keep omnibox + evidence rail only (per MVP_UI_IMPROVEMENTS.md)
- Minimal trust banner; feedback and translate controls only
- Acceptance: clean layout, no extraneous UI, passes accessibility contrast

#### Task 3.2: Basic Document Q&A
- Add upload affordance; show ingest skeleton; allow follow‑up questions over the file
- Acceptance: can ask one question about uploaded file; answer cites doc + statutes

### **Priority 4: Quality & RAG Polish (2 hours)**

#### Task 3.1: Response quality improvements
- **Current State**: RAG responses are working but could be more accurate
- **Required**: 
  - Test with 10-15 common legal questions
  - Adjust retrieval parameters if needed (top_k, min_score)
  - Improve OpenAI prompts for better response quality
- **Acceptance**: Responses are relevant and helpful for common queries
- **Effort**: 1 hour

#### Task 3.2: Error handling & user experience
- **Required**:
  - Add proper error messages for common failure scenarios
  - Improve loading states and user feedback
  - Add rate limiting to prevent abuse
- **Acceptance**: Graceful error handling, good user experience
- **Effort**: 1 hour

### **Priority 5: Documentation & Handoff (1 hour)**

#### Task 4.1: Update documentation
- **Required**: Update all documentation to reflect current state
- **Files to update**:
  - `README.md` - Update with deployment URL and usage instructions
  - `docs/QUICKSTART.md` - Update for production deployment
  - `docs/project/MVP_TASK_LIST.md` - Mark all completed tasks
- **Acceptance**: Documentation is current and accurate
- **Effort**: 0.5 hours

#### Task 4.2: Create handoff documentation
- **Required**: Document how to maintain and operate the MVP
- **Content**:
  - How to add new legal documents
  - How to monitor system health
  - How to update responses and prompts
  - Cost monitoring and optimization
- **Acceptance**: Clear operational documentation exists
- **Effort**: 0.5 hours

---

## 📋 **Task Summary**

| Priority | Task | Effort | Status |
|----------|------|---------|---------|
| 1.1 | Update WhatsApp to use RAG | 2h | 🔴 |
| 1.2 | WhatsApp Business API setup | 2h | 🔴 |
| 2.1 | Vercel environment variables | 1h | 🔴 |
| 2.2 | Deploy to Vercel | 1h | 🔴 |
| 2.3 | Verify production deployment | 1h | 🔴 |
| 3.1 | Enterprise less‑ink workspace UI | 1h | 🔴 |
| 3.2 | Basic Document Q&A | 1h | 🔴 |
| 4.1 | Response quality improvements | 1h | 🔴 |
| 4.2 | Error handling & UX polish | 1h | 🔴 |
| 5.1 | Update documentation | 0.5h | 🔴 |
| 5.2 | Create handoff documentation | 0.5h | 🔴 |

**Total Remaining Effort**: ~10 hours

---

## 🎯 **MVP Success Criteria**

When these tasks are complete, we will have:

1. **✅ Working RAG System**: End-to-end legal question answering
2. **✅ Multi-Channel Access**: Web interface + WhatsApp integration
3. **✅ Production Deployment**: Hosted on Vercel with proper scaling
4. **✅ Quality Responses**: Relevant, cited answers from Zimbabwe legal documents
5. **✅ Analytics & Feedback**: User engagement tracking and feedback collection
6. **✅ Operational Documentation**: Clear maintenance and operation guides

---

## 🚀 **Recommended Execution Order**

1. **Start with Task 1.1** (Update WhatsApp RAG) - High impact, builds on working RAG
2. **Then Task 2.1-2.3** (Vercel deployment) - Get production environment ready  
3. **Then Task 1.2** (WhatsApp API setup) - Complete WhatsApp integration
4. **Finally Tasks 3-4** (Polish & documentation) - Final touches

This gets us to a **production-ready MVP** that users can access via web and WhatsApp with intelligent legal responses powered by our RAG system.
