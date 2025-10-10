# Frontend Integration Guide
**RightLine Legal AI Backend API**  
**Last Updated**: October 9, 2025

---

## Quick Start

### Base URLs
```
Development: http://localhost:8000
Production:  https://api.gweta.co.zw (or your Vercel deployment)
```

### Authentication
All production endpoints require Firebase Authentication:

```typescript
import { getAuth, signInWithEmailAndPassword } from 'firebase/auth';

// 1. Initialize Firebase
const auth = getAuth(app);

// 2. Sign in user
const userCredential = await signInWithEmailAndPassword(auth, email, password);

// 3. Get ID token
const token = await userCredential.user.getIdToken();

// 4. Use token in API calls
const headers = {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
};
```

---

## Core Endpoints

### 1. Legal Query (Main Endpoint)

**POST** `/api/v1/query`

**Authentication**: Required (Firebase Bearer token)

**Rate Limit**: 10 requests/minute per user

**Request**:
```typescript
interface QueryRequest {
  text: string;           // Max 1024 chars, required
  lang_hint?: string;     // "en" | "sn", default: "en"
  channel: string;        // "web" | "whatsapp", default: "web"
  date_ctx?: string;      // ISO date e.g. "2023-10-26"
}
```

**Response**:
```typescript
interface QueryResponse {
  tldr: string;                    // Brief summary (max 220 chars)
  key_points: string[];            // 3-5 key points
  citations: Citation[];           // Source citations
  suggestions: string[];           // 2-3 follow-up questions
  confidence: number;              // 0.0-1.0
  source: string;                  // "hybrid" | "openai" | "extractive"
  request_id: string;              // For tracking/feedback
  processing_time_ms: number;      // Performance metric
}

interface Citation {
  title: string;
  url: string;
  page?: number;
  sha?: string;
}
```

**Example**:
```typescript
const response = await fetch('http://localhost:8000/api/v1/query', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-Session-ID': sessionId  // Optional: for session tracking
  },
  body: JSON.stringify({
    text: 'What are the requirements for forming a company in Zimbabwe?',
    channel: 'web'
  })
});

const data: QueryResponse = await response.json();

// Display to user
console.log(data.tldr);
console.log(data.key_points);
console.log(data.citations);
```

---

### 2. Streaming Query (Real-time Updates)

**GET** `/api/v1/query/stream?query={text}`

**Authentication**: Required

**Rate Limit**: 10 requests/minute

**Response**: Server-Sent Events (SSE)

**Event Types**:
```typescript
// meta: Processing started
{
  request_id: string;
  query: string;
  timestamp: string;
  user_id: string;
  status: 'processing';
}

// retrieval: Document search progress
{
  status: 'searching' | 'completed';
  message: string;
  results_count?: number;
  confidence?: number;
  progress: number;  // 0.0-1.0
}

// token: AI response streaming
{
  token: string;
  position: number;
  total_tokens: number;
}

// citation: Source document
{
  index: number;
  title: string;
  source: string;
  relevance: number;
}

// final: Complete response
{
  request_id: string;
  tldr: string;
  key_points: string[];
  citations_count: number;
  confidence: number;
  processing_time_ms: number;
  status: 'completed';
}

// error: Processing failed
{
  request_id: string;
  error: string;
  message: string;
  processing_time_ms: number;
}
```

**Example**:
```typescript
const queryParams = new URLSearchParams({ query: userQuery });
const eventSource = new EventSource(
  `http://localhost:8000/api/v1/query/stream?${queryParams}`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);

// Handle different event types
eventSource.addEventListener('meta', (event) => {
  const data = JSON.parse(event.data);
  setRequestId(data.request_id);
  setStatus('processing');
});

eventSource.addEventListener('retrieval', (event) => {
  const data = JSON.parse(event.data);
  setProgress(data.progress);
  if (data.status === 'completed') {
    setRetrievalResults(data.results_count);
  }
});

eventSource.addEventListener('token', (event) => {
  const data = JSON.parse(event.data);
  appendToken(data.token);
});

eventSource.addEventListener('citation', (event) => {
  const data = JSON.parse(event.data);
  addCitation(data);
});

eventSource.addEventListener('final', (event) => {
  const data = JSON.parse(event.data);
  setFinalResponse(data);
  eventSource.close();
});

eventSource.addEventListener('error', (event) => {
  const data = JSON.parse(event.data);
  showError(data.message);
  eventSource.close();
});

// Clean up on component unmount
return () => eventSource.close();
```

---

### 3. Submit Feedback

**POST** `/api/v1/feedback`

**Authentication**: Required

**Request**:
```typescript
interface FeedbackRequest {
  request_id: string;     // From QueryResponse
  rating: number;         // -1 (negative), 0 (neutral), 1 (positive)
  comment?: string;       // Optional, max 500 chars
}
```

**Response**:
```typescript
interface FeedbackResponse {
  success: boolean;
  message: string;
}
```

**Example**:
```typescript
await fetch('http://localhost:8000/api/v1/feedback', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    request_id: queryResponse.request_id,
    rating: 1,
    comment: 'Very helpful, thank you!'
  })
});
```

---

### 4. User Profile

**GET** `/api/v1/users/me`

**Authentication**: Required

**Response**:
```typescript
interface UserProfile {
  uid: string;
  email: string;
  created_at: string;
  // Additional profile fields
}
```

---

### 5. Waitlist (Public)

**POST** `/api/v1/waitlist`

**Authentication**: Not required (public endpoint)

**Request**:
```typescript
interface WaitlistRequest {
  email: string;
  name?: string;
  organization?: string;
}
```

---

## Error Handling

### Standard Error Response
```typescript
interface ErrorResponse {
  detail: string | {
    error_code: string;
    message: string;
    retry_after_seconds?: number;
  };
  request_id?: string;
}
```

### HTTP Status Codes
```
200 OK                - Request successful
400 Bad Request       - Invalid input (check detail for field errors)
401 Unauthorized      - Missing or invalid token
429 Too Many Requests - Rate limit exceeded (check Retry-After header)
500 Internal Error    - Server error (check request_id for debugging)
503 Service Unavailable - Dependencies down
```

### Error Handling Pattern
```typescript
async function queryLegalInfo(text: string): Promise<QueryResponse> {
  try {
    const token = await auth.currentUser?.getIdToken();
    if (!token) throw new Error('Not authenticated');
    
    const response = await fetch('http://localhost:8000/api/v1/query', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ text, channel: 'web' })
    });
    
    if (response.status === 401) {
      // Token expired - refresh
      const newToken = await auth.currentUser?.getIdToken(true);
      // Retry with new token
      return queryLegalInfo(text);
    }
    
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After');
      throw new Error(`Rate limited. Retry after ${retryAfter} seconds`);
    }
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Query failed');
    }
    
    return await response.json();
    
  } catch (error) {
    console.error('Query failed:', error);
    throw error;
  }
}
```

---

## Best Practices

### 1. Token Management
```typescript
// Refresh tokens before they expire
useEffect(() => {
  const interval = setInterval(async () => {
    if (auth.currentUser) {
      await auth.currentUser.getIdToken(true);
    }
  }, 50 * 60 * 1000); // Every 50 minutes (tokens last 1 hour)
  
  return () => clearInterval(interval);
}, []);
```

### 2. Request Tracking
```typescript
// Store request_id for feedback and debugging
const handleQuery = async (text: string) => {
  const response = await queryLegalInfo(text);
  
  // Save for feedback submission
  localStorage.setItem(
    `query_${response.request_id}`,
    JSON.stringify({ query: text, response })
  );
  
  return response;
};
```

### 3. Optimistic UI
```typescript
// Show loading state immediately
setLoading(true);

try {
  const response = await queryLegalInfo(text);
  setResult(response);
} catch (error) {
  showError(error.message);
} finally {
  setLoading(false);
}
```

### 4. Caching (Client-Side)
```typescript
// Cache responses to avoid redundant API calls
const queryCache = new Map<string, QueryResponse>();

async function cachedQuery(text: string): Promise<QueryResponse> {
  const cacheKey = text.toLowerCase().trim();
  
  if (queryCache.has(cacheKey)) {
    const cached = queryCache.get(cacheKey)!;
    // Return cached if less than 5 minutes old
    const age = Date.now() - cached.timestamp;
    if (age < 5 * 60 * 1000) {
      return cached;
    }
  }
  
  const response = await queryLegalInfo(text);
  queryCache.set(cacheKey, { ...response, timestamp: Date.now() });
  return response;
}
```

---

## Testing in Development

### Using curl
```bash
# Get a Firebase token (use Firebase Console or auth emulator)
export TOKEN="your-firebase-id-token"

# Test query endpoint
curl -X POST http://localhost:8000/api/v1/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is the minimum wage in Zimbabwe?",
    "channel": "web"
  }' | jq '.'

# Test rate limiting (run 11 times quickly)
for i in {1..11}; do
  echo "Request $i:"
  curl -X POST http://localhost:8000/api/v1/query \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"text": "test", "channel": "web"}' \
    -w "\nHTTP Status: %{http_code}\n"
done
```

### Using Postman/Insomnia
1. Set environment variables:
   - `baseUrl`: `http://localhost:8000`
   - `token`: Your Firebase ID token

2. Create requests:
   - POST `{{baseUrl}}/api/v1/query`
   - Headers: `Authorization: Bearer {{token}}`

---

## Performance Expectations

### Latency Targets
```
P50: < 2 seconds (with cache hit)
P95: < 5 seconds (with retrieval)
P99: < 15 seconds (complex queries with reranking)
```

### Caching
- Semantic cache: ~50ms response time for similar queries
- Exact cache: ~20ms response time for duplicate queries
- Cache TTL: 30 minutes

### Concurrency
- Supports 100+ concurrent requests (serverless auto-scales)
- Each request creates fresh connections (serverless pattern)
- No connection pooling required on client side

---

## Production Deployment

### Vercel Environment Variables

Set these in Vercel Dashboard → Project → Settings → Environment Variables:

```bash
# Application
RIGHTLINE_APP_ENV=production
RIGHTLINE_LOG_LEVEL=INFO
RIGHTLINE_DEBUG=false
RIGHTLINE_SECRET_KEY=<generate-new-secure-key>
RIGHTLINE_CORS_ORIGINS=https://gweta.vercel.app,https://www.gweta.co.zw

# AI Services
OPENAI_API_KEY=<production-openai-key>
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
MILVUS_ENDPOINT=<production-milvus-endpoint>
MILVUS_TOKEN=<production-milvus-token>
MILVUS_COLLECTION_NAME=legal_chunks_v3

# Firebase
FIREBASE_ADMIN_SDK_JSON=<base64-encoded-service-account-json>

# R2 Storage
CLOUDFLARE_R2_S3_ENDPOINT=<r2-endpoint>
CLOUDFLARE_R2_ACCESS_KEY_ID=<r2-access-key>
CLOUDFLARE_R2_SECRET_ACCESS_KEY=<r2-secret-key>
CLOUDFLARE_R2_BUCKET_NAME=gweta-prod-documents

# Optional: Monitoring
SENTRY_DSN=<sentry-dsn>
LANGCHAIN_API_KEY=<langsmith-key>
LANGCHAIN_PROJECT=gweta-production
LANGCHAIN_TRACING_V2=true
```

### Health Checks

```typescript
// Before making queries, verify API health
const health = await fetch('https://api.gweta.co.zw/healthz');
if (health.ok) {
  const data = await health.json();
  console.log('API Status:', data.status); // "healthy"
}
```

---

## Rate Limiting Handling

### Client-Side Implementation

```typescript
class RateLimitedAPIClient {
  private rateLimitResetTime: number | null = null;
  
  async query(text: string): Promise<QueryResponse> {
    // Check if we're still rate limited
    if (this.rateLimitResetTime && Date.now() < this.rateLimitResetTime) {
      const waitSeconds = Math.ceil((this.rateLimitResetTime - Date.now()) / 1000);
      throw new Error(`Rate limited. Please wait ${waitSeconds} seconds.`);
    }
    
    try {
      const response = await fetch('/api/v1/query', {
        method: 'POST',
        headers: await this.getHeaders(),
        body: JSON.stringify({ text, channel: 'web' })
      });
      
      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After');
        this.rateLimitResetTime = Date.now() + (parseInt(retryAfter || '60') * 1000);
        
        const error = await response.json();
        throw new Error(error.detail.message || 'Rate limit exceeded');
      }
      
      // Reset rate limit tracker on success
      this.rateLimitResetTime = null;
      
      return await response.json();
      
    } catch (error) {
      console.error('Query failed:', error);
      throw error;
    }
  }
  
  private async getHeaders(): Promise<Record<string, string>> {
    const token = await auth.currentUser?.getIdToken();
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    };
  }
}
```

---

## Monitoring & Debugging

### Request IDs
Every response includes a `request_id`. Use this for:
1. **Debugging**: Share with backend team to trace issues
2. **Feedback**: Link user feedback to specific queries
3. **Analytics**: Track query patterns

```typescript
// Store request_id with response
const response = await queryLegalInfo(text);
analytics.track('query_completed', {
  request_id: response.request_id,
  confidence: response.confidence,
  processing_time_ms: response.processing_time_ms
});
```

### Performance Monitoring
```typescript
// Track API performance
const startTime = performance.now();
const response = await queryLegalInfo(text);
const clientLatency = performance.now() - startTime;

console.log({
  server_processing_ms: response.processing_time_ms,
  network_latency_ms: clientLatency - response.processing_time_ms,
  total_latency_ms: clientLatency
});
```

---

## Common Issues & Solutions

### Issue: 401 Unauthorized
**Cause**: Token expired or invalid  
**Solution**:
```typescript
if (response.status === 401) {
  const newToken = await auth.currentUser?.getIdToken(true);
  // Retry request with new token
}
```

### Issue: 429 Rate Limit
**Cause**: Too many requests  
**Solution**: Implement exponential backoff
```typescript
async function queryWithRetry(text: string, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await queryLegalInfo(text);
    } catch (error) {
      if (error.status === 429 && i < maxRetries - 1) {
        const delay = Math.pow(2, i) * 1000; // Exponential backoff
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }
      throw error;
    }
  }
}
```

### Issue: Slow responses
**Cause**: Complex query or cold start  
**Solution**: Use streaming endpoint for better UX
```typescript
// Instead of waiting 15 seconds for response
const response = await queryLegalInfo(text); // ❌ User waits

// Stream updates in real-time
const eventSource = streamQuery(text); // ✅ User sees progress
```

### Issue: Empty citations
**Cause**: Low retrieval confidence or no matching documents  
**Solution**: Check confidence score
```typescript
if (response.confidence < 0.3) {
  showWarning('Limited information available. Results may be incomplete.');
}

if (response.citations.length === 0) {
  showWarning('No specific legal sources found. General information provided.');
}
```

---

## Security Best Practices

### 1. Never Expose Tokens
```typescript
// ❌ DON'T
localStorage.setItem('firebase_token', token);

// ✅ DO
// Firebase SDK handles token storage securely
const token = await auth.currentUser?.getIdToken();
```

### 2. Validate on Both Sides
```typescript
// Client-side validation (UX)
if (text.length > 1024) {
  showError('Query too long. Maximum 1024 characters.');
  return;
}

// Server validates anyway (security)
```

### 3. HTTPS Only in Production
```typescript
const baseUrl = process.env.NODE_ENV === 'production'
  ? 'https://api.gweta.co.zw'
  : 'http://localhost:8000';
```

### 4. Sanitize User Input
```typescript
// Prevent XSS when displaying results
const sanitize = (html: string) => {
  const div = document.createElement('div');
  div.textContent = html;
  return div.innerHTML;
};

// Display
<div>{sanitize(response.tldr)}</div>
```

---

## TypeScript Types

```typescript
// Save as src/types/api.ts

export interface QueryRequest {
  text: string;
  lang_hint?: 'en' | 'sn';
  channel: 'web' | 'whatsapp';
  date_ctx?: string;
}

export interface Citation {
  title: string;
  url: string;
  page?: number;
  sha?: string;
}

export interface QueryResponse {
  tldr: string;
  key_points: string[];
  citations: Citation[];
  suggestions: string[];
  confidence: number;
  source: string;
  request_id: string;
  processing_time_ms: number;
}

export interface FeedbackRequest {
  request_id: string;
  rating: -1 | 0 | 1;
  comment?: string;
}

export interface FeedbackResponse {
  success: boolean;
  message: string;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  service: string;
  version: string;
  timestamp: number;
}
```

---

## Next Steps

1. **Review this guide** with your frontend team
2. **Set up Firebase** in your frontend app
3. **Configure environment variables** (development vs production)
4. **Implement authentication flow** using Firebase SDK
5. **Test with development API** (localhost:8000)
6. **Deploy to staging** and test with staging API
7. **Deploy to production** and monitor closely

**Questions?** Check `/docs` endpoint for full OpenAPI specification.

---

**Last Updated**: October 9, 2025  
**API Version**: v1.0.0  
**Backend Status**: ✅ Production Ready (with rate limiting implemented)

