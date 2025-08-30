
# Gweta v2.0 Architecture — Advanced RAG & Agentic Systems

## 0) Product Promise (v2.0)

- **Deep, Multi-Source Answers**: Go beyond simple document retrieval. Synthesize information across multiple documents with clear citations and context-aware follow-ups.
- **Agentic Reasoning**: Decompose complex questions, automatically rewrite queries for clarity, and validate evidence before answering.
- **Stateful & Personalized**: Maintain conversational context within and across sessions, leveraging user history to provide more relevant and precise results.
- **Enterprise-Grade Security**: Ensure robust user authentication and data isolation from the ground up.
- **High-Performance & Low-Latency**: Target a **< 2.5s P95** response time for typical queries through optimized pipelines and intelligent caching.
- **Serverless & Scalable**: Built on Vercel and Firebase for a low-ops, pay‑per‑use, and tightly integrated infrastructure.

-----

## 1) High-Level Architecture (v2.0)

The architecture evolves from a simple pipeline to a lightweight agentic system. The core is an **Agentic Loop** that plans, executes, and validates the retrieval and synthesis process, enabling more complex reasoning and higher accuracy.

```
           ┌────────────────────────────────────┐
           │              Channels              │
           │ Web (Authenticated) | WhatsApp (Future) │
           └──────────────┬─────────────────────┘
                          │ (JWT Auth Token)
                   ┌──────▼───────────────────────────┐
                   │        API Layer (Vercel)       │
                   │ (FastAPI, Auth Middleware)      │
                   └──────┬────────────────────┬─────┘
                          │ (User Query)       │ (User Context & State)
      ┌───────────────────▼──────────────────┐ │ ┌───────────────────────┐
      │         Core Agentic Engine          │ │ │ Firebase              │
      │ ┌──────────────────────────────────┐ │ │ │ - Authentication      │
      │ │ 1. Agentic Loop & Query Planner  ├─┼─► │ - Firestore (Memory)  │
      │ │    - Decompose & Rewrite (HyDE)  │ │ │ - Firestore (Feedback)│
      │ └─────────────────┬────────────────┘ │ └───────────────────────┘
      │                   │ (Planned Sub-Queries)
      │ ┌─────────────────▼────────────────┐
      │ │  2. Multi-Strategy Retrieval     │
      │ │    - Hybrid Search (BM25 + Dense)│
      │ │    - Parent Document Retrieval   │
      │ │    - (Future: GraphRAG)          │
      │ └─────────────────┬────────────────┘
      │                   │ (Candidate Documents)
      │ ┌─────────────────▼────────────────┐
      │ │  3. Reranking & Evidence Check   │
      │ │    - BGE-Reranker v2             │
      │ │    - Validate sufficiency        │
      │ └─────────────────┬────────────────┘
      │                   │ (High-Quality Evidence)
      │ ┌─────────────────▼────────────────┐
      │ │   4. Synthesis & Composition     │
      │ │    - OpenAI GPT-4o-mini          │
      │ │    - Generate Answer & Citations │
      │ └─────────────────┬────────────────┘
      │                   │ (Final Answer)
      └───────────────────│──────────────────┘
                          │
                   ┌──────▼───────────────────────────┐
                   │             Data Stores           │
                   ├───────────────────┬───────────────┤
                   │ Milvus Cloud      │ Sparse Index  │
                   │ (Dense Vectors)   │ (e.g., BM25)  │
                   └───────────────────┴───────────────┘
```

-----

## 2) Core Components

### 2.1 Channels & API Layer (Unchanged)
- **Web Interface**: Authenticated frontend managing JWT tokens via Firebase Auth.
- **Vercel Functions (FastAPI)**: Protected endpoints for querying, feedback, and session history, validating tokens on each request.

### 2.2 Authentication & State (Firebase)
The two-tier memory system (Short-Term Session, Long-Term Profile) remains a core pillar for personalization and is now a key input into the agentic planner.

### 2.3 Advanced RAG Pipeline (Agentic & Multi-Strategy)

This is the core evolution, moving from a linear chain to a dynamic, query-aware agent.

#### a. The Agentic Loop: Query Planning & Decomposition
Instead of directly embedding a user's raw query, a lightweight "planner" LLM call happens first.

- **Responsibility**:
    1.  **Analyze Intent**: Is the query simple or complex?
    2.  **Query Rewrite/Expansion**: For simple queries, use techniques like **HyDE (Hypothetical Document Embeddings)** to generate a more detailed, embedding-friendly query.
    3.  **Decomposition**: For complex questions ("Compare and contrast X and Y"), break it down into multiple sub-queries that can be executed independently.
    4.  **Route**: (Future) Direct the query to the best retrieval strategy (e.g., vector search for semantic questions, GraphRAG for multi-hop reasoning).
- **Example**:
    - **User Query**: "What about for a private company?"
    - **Context (from Firestore)**: Previous question was "What are the registration requirements for a PBC?"
    - **Planner Action**: Rewrites the query to a standalone question: "What are the registration requirements for a Private Limited Company (PLC) in Zimbabwe?"

#### b. Multi-Strategy Retrieval
The system retrieves evidence using multiple techniques in parallel to improve recall.

- **Hybrid Search**: Combine the strengths of two search types:
    - **Dense Retrieval (Vector Search)**: Use Milvus with OpenAI embeddings (`text-embedding-3-small`) to find semantically similar documents. Excellent for concepts and meaning.
    - **Sparse Retrieval (Keyword Search)**: Use a lightweight BM25 index to find documents with exact keyword matches. Critical for acronyms, specific names, and legal jargon.
- **Parent Document / Small-to-Big Retrieval**:
    - Chunks are kept small and specific for high-precision matching during retrieval.
    - Once the best small chunks are identified, the system retrieves their larger "parent" documents.
    - This provides the synthesis LLM with broader context, reducing the risk of generating answers from fragmented or incomplete information.

#### c. Reranking & Evidence Validation
This step ensures only the most relevant information reaches the final synthesis stage.

- **Reranking**: The top ~50-100 candidate documents from the hybrid search are passed to a more powerful and precise reranker model (e.g., `BGE-reranker-v2`). This model re-scores the documents based on their direct relevance to the original query.
- **Evidence Check**: The agentic loop can perform a quick validation step here. An LLM call checks if the reranked documents seem sufficient to answer the question. If not, it can trigger another retrieval cycle with a modified query.

#### d. Synthesis & Composition
The final, high-quality evidence is used to generate the user-facing answer.

- **Model**: `gpt-4o-mini` remains the primary choice for its balance of cost, speed, and capability.
- **Personalized & Grounded Prompt**: The prompt is enriched with user context and strict instructions.
  > *"You are a Zimbabwean legal AI assistant. The user you are helping has shown past interest in [long\_term\_summary]. Answer the question **only using the provided legal texts**. Cite your sources meticulously using the format [doc_id, chunk_id]. If the answer is not in the texts, state that clearly. Here is the recent conversation history for context: [session\_history]."*

### 2.4 Chunking & Embedding Strategy

- **Strategy**: Implement "Small-to-Big" retrieval.
    1.  **Chunking**: Documents are split into small, semantically coherent chunks (e.g., 256 tokens). Each chunk stores a reference to its parent document ID.
    2.  **Embedding**: Only the small chunks are embedded and stored in Milvus.
    3.  **Retrieval**: The retrieval process (hybrid search + reranking) operates on these small chunks to find the most precise matches.
    4.  **Expansion**: Before passing the context to the synthesis LLM, the system fetches the full parent documents corresponding to the top-ranked small chunks.

### 2.5 Data Stores

- **Vector Store**: Milvus Cloud (Dense Embeddings).
- **Sparse Index**: A simple in-memory or file-based BM25 index (e.g., using the `rank-bm25` library) can be used for the MVP. For scaling, this could be moved to a dedicated search service like OpenSearch.
- **State & User Data**: Firestore (unchanged).
- **(Future) Graph Database**: For GraphRAG capabilities, a graph database like Neo4j would be introduced to store entities and relationships extracted from the corpus.

-----

## 3) Enhanced Feedback Loop (Unchanged)
The existing feedback mechanism using Firestore is robust and provides a high-quality dataset for future fine-tuning and evaluation of the more complex RAG pipeline.

-----

## 4) Security & Privacy (Unchanged)
JWT validation and Firestore Security Rules remain the cornerstone of the security model, ensuring users can only access their own data.

-----

## 5) Non-Functional Requirements

- **Latency**: The P95 target of <2.5s is more aggressive given the multi-step agentic process. Each LLM call in the planner and validation step adds latency. Caching strategies and optimizing the retrieval stack will be critical.
- **Cost**: The agentic loop introduces additional LLM calls, increasing operational costs. The trade-off is a significant increase in accuracy and reasoning capability. Start with a simple rewrite and add more complex decomposition as needed.
- **Modularity**: The pipeline should be designed in a modular way, allowing different strategies (e.g., HyDE vs. multi-query, different rerankers) to be swapped in and out for evaluation.

This architecture provides a robust foundation for building a truly next-generation, reliable, and personalized AI research assistant.