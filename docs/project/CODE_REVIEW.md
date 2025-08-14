## Code Review

### Task 1.1.1 — Minimal FastAPI Service

Scope reviewed
- `services/api/main.py`
- `services/api/models.py`
- `services/api/responses.py`
- `services/api/__init__.py`
- Tests in `tests/unit/services/api/`

Verdict
- Meets acceptance criteria: service boots, `/healthz` works, `/v1/query` returns mock data with structured payload and citations.
- Quality aligns well with `.cursorrules` and the architecture for MVP scope.

What’s excellent (kept)
- Async FastAPI app with `ORJSONResponse` default and structured logging via `structlog`.
- Input validation caps and sanitization (text length ≤ 1000, channel whitelist) in `QueryRequest`.
- Clean request logging middleware with request ID and duration, plus header injection.
- Clear Pydantic response models for `SectionRef`, `Citation`, `QueryResponse`.
- Hardcoded response corpus organized with simple normalization + keyword scoring that is deterministic and fast (good for MVP latency).
- Health and readiness endpoints present and simple.
- Good test coverage across endpoints and response logic; realistic assertions on structure and behavior.

Gaps vs `.cursorrules` and architecture (actionable)
- Fixed response schema for /v1/query
  - `.cursorrules` states the response shape is fixed: `summary_3_lines`, `section_ref`, `citations[]`, `confidence`, `related_sections[]`.
  - Current `QueryResponse` adds `request_id` and `processing_time_ms` which surface as `null` fields in responses. This violates the fixed shape.
  - Recommendation: remove these fields from `QueryResponse` or set `response_model_exclude_none=True` on the route and avoid including extra fields in the model for `/v1/query`.

- Security headers middleware
  - `.cursorrules [api/**]` asks to add security headers.
  - Recommendation: add a small middleware to set `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, and `X-XSS-Protection`.

- GZip compression
  - `.cursorrules [api/**]` suggests enabling gzip.
  - Recommendation: add `GZipMiddleware` with a conservative minimum size.

- Request time budget enforcement
  - Architecture/time budget suggests a 2s overall cap.
  - Recommendation: wrap handler logic with `asyncio.timeout(settings.api_timeout_ms / 1000)` to enforce budget and return a safe 503 on timeout.

- Error response normalization
  - You defined `ErrorResponse` but do not register exception handlers. `.cursorrules` encourages mapping internal errors to safe shapes.
  - Recommendation: add handlers for `RequestValidationError` and generic `HTTPException` to return a consistent error schema.

- Settings friction for MVP run
  - `Settings` requires `secret_key`, `database_url`, `redis_url` even when unused in this MVP path.
  - Recommendation: mark DB/Redis as optional or provide dev defaults to reduce boot friction during Phase 1.

Minor polish (non-blocking)
- Remove unused imports (e.g., `typing.Any`, `logging`) in `main.py`.
- Consider adding a minimal `/` welcome route returning 200 + service/version for friendlier local checks.

Tests
- Good breadth: health/readiness, query success/fallback, validation errors, header assertions, normalization and scoring behavior.
- Suggested additions (later phases): exception-handler contract tests once standardized error responses are added.

Sample diffs (illustrative)

Exclude None fields (interim mitigation) on the route if retaining optional fields in the model:

```services/api/main.py
@app.post("/v1/query", response_model=QueryResponse, response_model_exclude_none=True, tags=["Query"])
async def query_legal_information(...):
    ...
```

Add gzip + basic security headers:

```services/api/main.py
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=512)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-XSS-Protection", "1; mode=block")
    return response
```

Enforce a request timeout budget:

```services/api/main.py
import asyncio

@app.post("/v1/query", response_model=QueryResponse, tags=["Query"])
async def query_legal_information(request: Request, query_request: QueryRequest) -> QueryResponse:
    settings = get_settings()
    async with asyncio.timeout(settings.api_timeout_ms / 1000):
        ...
```

Conclusion
- Strong MVP that cleanly satisfies Task 1.1.1. The core improvements to align perfectly with `.cursorrules` are (1) lock the response schema by removing extra nullable fields, (2) add security headers and gzip middleware, and (3) enforce a simple request time budget. Everything else is optional polish suitable for subsequent tasks.


