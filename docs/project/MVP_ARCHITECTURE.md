
# Gweta v1.5 Architecture — AI-Native Personalized Research

## 0\) Product Promise (Enhanced)

  - **Personalized, research-grade answers** with citations and context-aware follow-ups.
  - **Stateful conversations** that remember previous interactions within and across sessions.
  - **Enterprise-grade security** with user authentication and data isolation.
  - **\< 2.0s P95** response for typical queries, with intelligent caching for repeated queries.
  - **Minimal data collection** by default, with clear user consent for personalization features.
  - **Serverless on Vercel + Firebase**; low-ops, pay‑per‑use, and tightly integrated.

-----

## 1\) High-Level Architecture (Enhanced)

The core change is the introduction of a dedicated state management layer with Firebase, turning the stateless Vercel functions into an intelligent, user-aware backend.

```
           ┌────────────────────────────────────┐
           │              Channels              │
           │ Web (Authenticated) | WhatsApp (Future) │
           └──────────────┬─────────────────────┘
                          │ (JWT Auth Token)
                   ┌──────▼───────────────────────────┐
                   │          Vercel Functions       │
                   │ (FastAPI via Mangum, Stateful)  │
                   └──────┬────────────────────┬─────┘
                          │ (RAG Pipeline)     │ (User Context & State)
      ┌───────────────────▼──────────────────┐ │ ┌───────────────────────┐
      │        Core RAG Pipeline           │ │ │ Firebase              │
      │ - Context Injection (Firestore)    │ │ │ - Authentication      │
      │ - Query Transformation             │ │ │ - Firestore (Memory)  │
      │ - Vector Search (Milvus Cloud)     │ └─► │ - Firestore (Feedback)│
      │ - Hybrid Retrieval + Reranking     │   └───────────────────────┘
      │ - OpenAI GPT-4o-mini Composition   │
      └─────────┬──────────────────────────┘
                │
        ┌───────▼─────────┐          ┌───────────────────┐
        │  Milvus Cloud   │          │    OpenAI APIs    │
        │  Vector Store   │          │ - Embeddings      │
        └─────────────────┘          │ - Composition     │
                                     └───────────────────┘
```

-----

## 2\) Core Components (Enhanced & Stateful)

### 2.1 Channel (Authenticated)

  - **Gweta Web (Enterprise)**: Now a fully authenticated experience. Users log in to access their history, personalized suggestions, and saved research. The frontend will manage JWT tokens received from Firebase Auth.

### 2.2 Vercel Functions (FastAPI)

  - **Authentication Middleware**: All key endpoints are now protected. A dependency or middleware will verify the `Authorization: Bearer <token>` header against Firebase Auth on every request.
  - **Enhanced Endpoints**:
      - `/api/v1/query` (POST, Auth required): Now accepts a `session_id` to maintain conversation state.
      - `/api/v1/feedback` (POST, Auth required): Stores detailed feedback in a dedicated Firestore collection, linked to the user, session, and query.
      - `/api/v1/sessions` (GET, Auth required): Fetches user's past conversation history.
      - `/api/v1/sessions/{session_id}` (GET, Auth required): Fetches messages for a specific session.

### 2.3 Authentication & User Identity (Firebase)

  - **Provider**: Firebase Authentication (Email/Password, Google, etc.).
  - **Flow**:
    1.  Frontend client handles user sign-up/sign-in using Firebase SDK.
    2.  Upon success, Firebase returns a JWT token to the client.
    3.  Client stores this token (e.g., in `localStorage`) and includes it in the header of all API requests to Vercel.
    4.  A `users` collection in Firestore is created on first sign-up to store profile information and long-term memory summaries.

### 2.4 Memory & Context Management (Firestore)

This introduces a powerful two-tier memory system.

  - **Short-Term (Session) Memory**:

      - **Storage**: A `sessions` sub-collection under each user in Firestore. Each document in this collection represents a message (`role: 'user' | 'assistant'`, `content: '...'`, `timestamp`).
      - **Function**: Before running the RAG pipeline, the Vercel function fetches the last 5-10 messages from the current session. This history is used for **Query Transformation**.
      - **Example**: If the user asks "What about for a private company?", the history is passed to a preliminary LLM call to transform the query into a standalone question: "What are the registration requirements for a private company in Zimbabwe?" This transformed query is then sent to Milvus.

  - **Long-Term (Profile) Memory**:

      - **Storage**: A `long_term_summary` field within the user's document in the `users` collection.
      - **Function**: A background process (e.g., a Vercel Cron Job or a function triggered at the end of a session) periodically summarizes conversation sessions into key topics of interest.
      - **Example Summary**: `"User frequently researches topics related to corporate law, specifically the 'Companies and Other Business Entities Act' and requirements for PBCs."`
      - **Application**: This summary is injected into the RAG pipeline to **boost retrieval**. Keywords from the summary can be added to the Milvus query or used as a metadata filter to surface more relevant documents.

### 2.5 RAG Pipeline (Context-Aware)

  - **Implementation**: The pipeline now has a context-injection step at the beginning.
  - **Enhanced Retrieval Flow**:
    1.  **Context Injection**: On receiving a query, fetch the user's short-term (session history) and long-term (profile summary) memory from Firestore.
    2.  **Query Transformation**: Use the session history to rephrase the user's query into a standalone, context-rich question.
    3.  **Embedding**: OpenAI `text-embedding-3-small`.
    4.  **Personalized Vector Search**:
          - Perform similarity search in Milvus.
          - **Boost** results using keywords from the user's long-term summary. For instance, if the summary mentions "tax law," documents with that metadata get a higher score.
    5.  **Reranking**: Use a more advanced reranker (e.g., Cohere Rerank or a local cross-encoder model) for higher precision on the top-k results from Milvus.
  - **Enhanced Composition (OpenAI)**:
      - **Model**: Default to `gpt-4o-mini` for its superior cost-performance ratio and structured output capabilities.
      - **Personalized Prompt**: The system prompt now includes user context.
        > *"You are a Zimbabwean legal AI assistant. The user you are helping has shown past interest in [insert long\_term\_summary]. Answer the following question based on the provided legal texts. Here is the recent conversation history for context: [insert session\_history]."*

### 2.6 Data Stores (Centralized on Firebase & Milvus)

  - **Vector Store**: Milvus Cloud (unchanged).
  - **State & User Data**: Firestore (replaces Vercel KV).
  - **Firestore Collections Schema**:

<!-- end list -->

```json
// /users/{firebase_auth_uid}
{
  "email": "user@example.com",
  "created_at": "timestamp",
  "long_term_summary": "Researches corporate law, PBCs.",
  "preferences": { "language": "en" }
}

// /users/{firebase_auth_uid}/sessions/{session_id}/messages/{message_id}
{
  "role": "user" | "assistant",
  "content": "What is the process for registering a PBC?",
  "timestamp": "timestamp",
  "citations": [ { "doc_id": "COBEA_24_31", "chunk_id": 123 } ] // For assistant messages
}

// /feedback/{feedback_id}
{
  "user_id": "firebase_auth_uid",
  "session_id": "session_id",
  "query": "What is a PBC?",
  "response": "A Private Business Corporation is...",
  "rating": "thumbs_up" | "thumbs_down",
  "comment": "This answer was very helpful!",
  "timestamp": "timestamp"
}
```

-----

## 3\) Enhanced Feedback Loop

  - **Actionable Data**: Storing feedback in Firestore allows for powerful analysis. You can now track which users are unsatisfied, what topics are causing confusion, and correlate poor responses with specific legal documents.
  - **Automated Improvement**: This structured feedback becomes a high-quality dataset for future fine-tuning of models or evaluating changes to your RAG pipeline.

-----

## 4\) Security & Privacy (Enhanced)

  - **Authentication**: JWT validation on all serverless function calls.
  - **Authorization**: **Firestore Security Rules** are critical. They ensure a logged-in user can *only* read and write their own data (`/users/{userId}`).
    ```
    match /users/{userId}/{document=**} {
      allow read, write: if request.auth.uid == userId;
    }
    ```
  - **Data Privacy**: A clear privacy policy is now mandatory. Users must be informed that their conversation history is being stored to provide personalization features. Provide an option to clear history.

-----

## 5\) Non-Functional Requirements (Refined)

  - **Latency**: The P95 target of \<2s is now more challenging due to Firestore reads. Aggressive caching of user profiles and session data in the Vercel function's memory (for the duration of its execution) will be necessary.
  - **Cost**:
      - **Firebase**: The Spark (free) plan is very generous with Firestore reads/writes and 10k/month phone auth. This should cover the initial user base. The Blaze (pay-as-you-go) plan is cost-effective for scaling.
      - **OpenAI**: Costs will increase slightly due to the additional "query transformation" LLM call, but this is a high-value trade-off for accuracy.

This enhanced architecture moves GWeta from a stateless information retrieval engine to a true, personalized AI assistant. It creates a powerful foundation for future features like agentic tools, document uploads, and collaborative research.