# API Documentation

## Overview

Gweta provides a RESTful API for legal information queries. The API is designed for low latency and high reliability.

## Base URL

- **Production**: `https://api.gweta.zw/v1`
- **Staging**: `https://staging-api.gweta.zw/v1`
- **Local**: `http://localhost:8000/v1`

## Authentication

Currently, the API is open for MVP development. Production will require API keys:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.gweta.zw/v1/query
```

## Endpoints

### Query Endpoint

**POST** `/v1/query`

Submit a legal question and receive relevant statute sections.

#### Request

```json
{
  "text": "What is the penalty for theft?",
  "lang_hint": "en",
  "date_ctx": "2024-01-01",
  "channel": "whatsapp"
}
```

#### Response

```json
{
  "summary_3_lines": "Theft carries imprisonment up to 10 years.\nFine may be imposed instead or in addition.\nCourt considers value and circumstances.",
  "section_ref": {
    "act": "Criminal Law Act",
    "chapter": "9:23", 
    "section": "113",
    "version": "2024"
  },
  "citations": [
    {
      "title": "Criminal Law (Codification and Reform) Act",
      "url": "https://...",
      "page": 47,
      "sha": "abc123..."
    }
  ],
  "confidence": 0.92,
  "related_sections": ["114", "115", "88"]
}
```

### Search Sections

**GET** `/v1/sections/search`

Search for specific law sections.

#### Parameters

- `q` (string, required): Search query
- `limit` (integer, optional): Max results (default: 10)
- `act` (string, optional): Filter by act name
- `date` (string, optional): As-at date (ISO format)

#### Example

```bash
curl "https://api.rightline.zw/v1/sections/search?q=traffic&limit=5"
```

### Health Check

**GET** `/health`

Check API service health.

#### Response

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "production",
  "timestamp": "2024-08-13T10:00:00Z"
}
```

## Rate Limiting

- **Default**: 60 requests per minute
- **Authenticated**: 300 requests per minute
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## Error Responses

### 400 Bad Request

```json
{
  "error": "validation_error",
  "message": "Invalid request format",
  "details": {
    "field": "text",
    "issue": "Required field missing"
  }
}
```

### 429 Too Many Requests

```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded",
  "retry_after": 30
}
```

### 500 Internal Server Error

```json
{
  "error": "internal_error",
  "message": "An error occurred processing your request",
  "request_id": "req_abc123"
}
```

## Language Support

Supported language codes:
- `en` - English
- `sn` - Shona
- `nd` - Ndebele

## Pagination

For endpoints returning multiple results:

```json
{
  "results": [...],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total": 45,
    "pages": 5
  }
}
```

## Webhooks

For async operations, webhooks can be configured:

```json
{
  "webhook_url": "https://your-server.com/webhook",
  "events": ["query.completed", "document.processed"]
}
```

## SDKs

Coming soon:
- Python SDK
- JavaScript/TypeScript SDK
- PHP SDK

## OpenAPI Specification

Full OpenAPI 3.0 specification available at:
- JSON: `/openapi.json`
- Interactive docs: `/docs`
- ReDoc: `/redoc`

## Support

For API support, please contact:
- GitHub Issues: [Report an issue](https://github.com/Lunexa-AI/right-line/issues)
- Email: api-support@gweta.zw (coming soon)
