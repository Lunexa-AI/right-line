# Waitlist Implementation Task List

This document outlines the detailed tasks required to implement a waitlist system for collecting user email addresses before full launch.

---

## Overview

**Goal**: Implement a minimal, secure waitlist system that allows visitors to submit their email address without authentication. Data is stored in Firestore with proper validation, rate limiting, and analytics tracking.

**Target API**: `POST /api/v1/waitlist`

**Estimated Time**: 2-3 hours including comprehensive tests

---

## Task Breakdown

### Phase 1: Data Models & Firestore Setup

#### 1.1. Create Firestore Data Model ✅
- **Task**: Add `WaitlistEntry` model to `libs/models/firestore.py`
- **Requirements**:
  - `waitlist_id: str` (UUID primary key)
  - `email: EmailStr` (validated email address)
  - `joined_at: datetime` (UTC timestamp)
  - `source: str` (tracking channel: "web", "referral", etc.)
  - `metadata: dict[str, str] | None` (optional: IP, user agent for analytics)
- **Validation**: Email format, required fields, timestamp auto-generation

#### 1.2. Create API Request/Response Models ✅
- **Task**: Add waitlist models to `api/models.py`
- **Models to create**:
  - `WaitlistRequest`: Email validation, optional source field
  - `WaitlistResponse`: Success status, message, duplicate flag
- **Validation**: Pydantic email validation, input sanitization

#### 1.3. Implement Firestore Operations ✅
- **Task**: Create `libs/firestore/waitlist.py`
- **Functions to implement**:
  - `add_to_waitlist(client, email, source, metadata)` → Returns (created: bool, entry: WaitlistEntry)
  - `check_email_exists(client, email)` → Returns bool
  - `get_waitlist_stats(client)` → Returns count, latest entries (for admin)
- **Requirements**: Idempotent operations, proper error handling, async/await

### Phase 2: API Endpoint Implementation

#### 2.1. Create Waitlist Router ✅
- **Task**: Create `api/routers/waitlist.py`
- **Endpoint**: `POST /api/v1/waitlist`
- **Features**:
  - Email validation and sanitization
  - Duplicate handling (graceful, not error)
  - Source tracking
  - Structured logging
  - Rate limiting preparation (headers/metadata collection)

#### 2.2. Rate Limiting & Security ✅
- **Task**: Implement basic security measures
- **Requirements**:
  - Collect IP address and User-Agent for rate limiting
  - Input sanitization (strip whitespace, lowercase email)
  - Honeypot field detection (optional hidden field for bot detection)
  - Request size limits (already handled by FastAPI)
- **Future**: Integration point for Redis-based rate limiting

#### 2.3. Update Main Router ✅
- **Task**: Add waitlist router to `api/main.py`
- **Requirements**: Include router with proper tags and prefix

### Phase 3: Comprehensive Testing

#### 3.1. Unit Tests for Firestore Operations ✅
- **Task**: Create `tests/libs/test_waitlist_firestore.py`
- **Test Cases**:
  - Add new email to waitlist (success)
  - Add duplicate email (idempotent behavior)
  - Invalid email format handling
  - Firestore connection failures
  - Concurrent access scenarios

#### 3.2. API Integration Tests  
- **Task**: Create `tests/api/test_waitlist_api.py`
- **Test Cases**:
  - Valid email submission (201 Created)
  - Duplicate email submission (200 OK, already_subscribed: true)
  - Invalid email formats (422 Validation Error)
  - Empty/missing email (422 Validation Error)
  - Request size limits
  - Response format validation

#### 3.3. End-to-End Tests
- **Task**: Create `test_waitlist_e2e.py` (root level)
- **Test Cases**:
  - Full flow: request → validation → Firestore → response
  - Error scenarios with proper HTTP codes
  - Load testing (basic - multiple concurrent requests)

### Phase 4: Security & Observability

#### 4.1. Logging & Analytics
- **Task**: Implement structured logging in waitlist operations
- **Requirements**:
  - Log successful additions with metadata
  - Log duplicate attempts (for analytics)
  - Log validation failures
  - Log Firestore errors with context
- **Format**: JSON structured logs compatible with existing telemetry

#### 4.2. Error Handling & Monitoring
- **Task**: Implement comprehensive error handling
- **Error Cases**:
  - Firestore unavailable (503 Service Unavailable)
  - Invalid email format (422 Validation Error)
  - Rate limit exceeded (429 Too Many Requests) - future
  - Internal server errors (500 Internal Server Error)

#### 4.3. Basic Abuse Prevention
- **Task**: Implement basic security measures
- **Features**:
  - IP tracking in metadata
  - User-Agent logging
  - Honeypot field support (frontend integration point)
  - Input sanitization and normalization

### Phase 5: Documentation & Admin Features

#### 5.1. API Documentation
- **Task**: Ensure proper OpenAPI documentation
- **Requirements**:
  - FastAPI auto-documentation integration
  - Example requests/responses
  - Error code documentation
  - Rate limiting information

#### 5.2. Admin Functionality (Optional)
- **Task**: Create basic admin endpoint for waitlist stats
- **Endpoint**: `GET /api/v1/admin/waitlist/stats` (future authentication required)
- **Response**: Total count, recent signups, growth metrics
- **Security**: Placeholder for admin authentication

#### 5.3. Export Functionality (Future-Proofing)
- **Task**: Design export structure for marketing integration
- **Format**: CSV/JSON export capability
- **Privacy**: GDPR-ready structure
- **Integration**: Email marketing platform compatibility

---

## Technical Requirements

### Dependencies
- **Existing**: No new dependencies required
- **Validation**: Pydantic EmailStr (already available)
- **UUID**: Python built-in uuid module
- **Async**: AsyncIO and existing Firestore async client

### Database Schema
```
Collection: waitlist
Document ID: {auto-generated-uuid}
Fields:
  - waitlist_id: string (same as document ID)
  - email: string (lowercase, validated)
  - joined_at: timestamp (UTC)
  - source: string (default: "web")
  - metadata: map (optional, for analytics)
    - ip_address: string
    - user_agent: string
```

### API Specification
```yaml
POST /api/v1/waitlist:
  Request:
    email: string (required, email format)
    source: string (optional, default: "web")
  
  Responses:
    201: Successfully added to waitlist
    200: Already subscribed (idempotent)
    422: Validation error (invalid email)
    429: Rate limit exceeded (future)
    503: Service temporarily unavailable
```

---

## Success Criteria

### Functional Requirements
- ✅ Accepts valid email addresses
- ✅ Stores data in Firestore with timestamp
- ✅ Handles duplicate emails gracefully
- ✅ Returns appropriate HTTP status codes
- ✅ Validates email format strictly
- ✅ Tracks source/analytics metadata

### Non-Functional Requirements
- ✅ Response time < 500ms (P95)
- ✅ 100% test coverage for core functionality
- ✅ Proper error handling and logging
- ✅ Security best practices implemented
- ✅ API documentation auto-generated

### Security Requirements
- ✅ Input validation and sanitization
- ✅ Basic abuse prevention measures
- ✅ No sensitive data exposure
- ✅ Audit trail via structured logging

---

## Future Enhancements (Not in Scope)

### Phase 2 Features
- Redis-based rate limiting (5 requests/hour/IP)
- Email verification with confirmation link
- Admin dashboard for waitlist management
- Integration with email marketing platforms
- A/B testing for different signup flows

### Analytics Features
- Conversion tracking (waitlist → signup)
- Source attribution and campaign tracking
- Geographic distribution analytics
- Time-series signup metrics

### Privacy & Compliance
- GDPR compliance features
- Email opt-out mechanism
- Data retention policies
- Privacy policy integration

---

## Implementation Order

1. **Start with Data Models** (1.1, 1.2) - Foundation
2. **Implement Core Logic** (1.3, 2.1) - Business logic
3. **Add Security & Routing** (2.2, 2.3) - API layer
4. **Comprehensive Testing** (3.1, 3.2, 3.3) - Quality assurance
5. **Observability** (4.1, 4.2, 4.3) - Production readiness
6. **Documentation** (5.1, 5.2) - Finalization

**Total Estimated Time**: 2-3 hours for core implementation + tests
**Production Ready**: Add 1-2 hours for advanced security and monitoring
