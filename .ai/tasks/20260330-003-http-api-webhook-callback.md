# Task: HTTP API for External Job Submission with Webhook Callbacks

## Metadata
- **Status**: 📋 Ready
- **Priority**: MEDIUM
- **Created**: 2026-03-30
- **Category**: Feature / API Extension

## Summary

Add HTTP API endpoint to allow external services (e.g., Cloudflare Workers) to submit download jobs. Process asynchronously and callback with results using TerminalOutcomeResult structure.

## API Design

### Endpoint
```
POST /api/jobs
```

### Request Body
```json
{
  "url": "https://youtube.com/watch?v=...",
  "callback_url": "https://my-worker.cloudflare.workers/webhook",
  "format_preference": "mp4"  // optional
}
```

### Response (Immediate)
```json
{
  "job_id": "uuid-...",
  "status": "queued",
  "submitted_at": "2026-03-30T21:00:00Z"
}
```

### Webhook Callback (Async)
```json
{
  "job_id": "uuid-...",
  "submitted_url": "https://youtube.com/watch?v=...",
  "status": "completed",
  "outcome": {
    "outcome_kind": "completed",
    "media_kind": "video",
    "attempted_count": 1,
    "delivered_count": 1,
    "cached_count": 0,
    "failure_kind": null,
    "error_text": null
  },
  "files": [
    {
      "filename": "video_abc123.mp4",
      "size_bytes": 12345678,
      "duration_seconds": 120,
      "download_url": "https://bot.example.com/files/uuid/video_abc123.mp4?token=...",
      "expires_at": "2026-03-31T21:00:00Z"
    }
  ],
  "processing": {
    "started_at": "2026-03-30T21:00:01Z",
    "completed_at": "2026-03-30T21:00:45Z",
    "duration_ms": 44000
  }
}
```

**Status values**: `queued|processing|completed|failed|partial`

**Coherency note**: `outcome` field uses existing TerminalOutcomeResult structure from DOWN_AND_UP/terminal_outcome_result.py

## Architecture

### Components

| Component | File | Purpose |
|-----------|------|---------|
| HTTP Endpoint | `web/api_jobs.py` | FastAPI router for /api/jobs |
| Job Queue | `DATABASE/job_queue.py` | Simple in-memory or Redis queue |
| Worker | `HELPERS/job_worker.py` | Background job processor |
| File Server | `web/file_server.py` | Serve temporary file downloads |
| Webhook Client | `HELPERS/webhook_client.py` | POST callbacks with retry |

### Data Flow

```
1. External Service → POST /api/jobs
   ↓
2. API validates → Generate job_id → Queue job
   ↓
3. Return {job_id, status: "queued"} immediately
   ↓
4. Background Worker picks up job
   ↓
5. Worker executes download using existing handlers
   ↓
6. On completion: POST to callback_url
   ↓
7. Files available at download_url for 24h
```

## Implementation Notes

### Job Queue Options

**Option A: In-memory (asyncio.Queue)**
- Pros: Simple, no dependencies
- Cons: Jobs lost on restart
- Use if: Low volume, can retry on failure

**Option B: Redis (rq or arq)**
- Pros: Persistence, retries, monitoring
- Cons: Requires Redis
- Use if: Production volume, reliability critical

**Option C: PostgreSQL (if already using)**
- Pros: Existing infra, durable
- Cons: More complex polling

**Recommendation**: Start with A, migrate to B if needed.

### File Serving

Temporary file serving with signed URLs:

```python
# Generate signed URL valid for 24h
download_url = generate_signed_url(
    file_path="users/123/video_abc123.mp4",
    expires_in=86400,
    token_secret=Config.FILE_SERVE_SECRET
)
```

File server validates token, serves file, tracks access.

### Webhook Delivery

Use existing retry pattern from TaskPlanExecutor:
- Retry 3x with exponential backoff
- Log failures for manual retry
- Consider webhook status endpoint for debugging

## Existing Infrastructure to Reuse

- **Download logic**: `DOWN_AND_UP/down_and_up.py` handlers
- **Task/Plan execution**: `DOWN_AND_UP/task_plan_executor.py`
- **Terminal outcomes**: `DOWN_AND_UP/terminal_outcome_result.py`
- **Observability**: `HELPERS/task_debug.py` for tracing
- **FastAPI app**: `web/dashboard_app.py` (add router)

## Security Considerations

1. **API Authentication**: Bearer token or API key
2. **Callback verification**: HMAC signature or pre-shared secret
3. **File URLs**: Time-limited signed tokens
4. **Rate limiting**: Per-API-key limits
5. **URL validation**: Only allowlisted domains (configurable)

## Testing

```bash
# Submit job
curl -X POST http://localhost:5555/api/jobs \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://...", "callback_url": "https://..."}'

# Check webhook receives callback
# Verify file download works
# Verify TerminalOutcomeResult structure
```

## Dependencies

New dependencies likely needed:
```
pydantic  # Already have for FastAPI
# Option: redis for job queue
# Option: cryptography for signed URLs
```

## Files to Create/Modify

**New files**:
- `web/api_jobs.py` - FastAPI router
- `DATABASE/job_queue.py` - Queue abstraction
- `HELPERS/job_worker.py` - Background worker
- `HELPERS/webhook_client.py` - Webhook delivery
- `web/file_server.py` - File serving (or extend dashboard)

**Modified files**:
- `web/dashboard_app.py` - Include api_jobs router
- `CONFIG/config.py` - Add FILE_SERVE_SECRET, API_KEYS

## Acceptance Criteria

- [ ] POST /api/jobs accepts URL and callback_url
- [ ] Returns job_id immediately (async processing)
- [ ] Background worker processes downloads
- [ ] Webhook callback sent on completion/failure
- [ ] Callback payload uses TerminalOutcomeResult structure
- [ ] Files available at signed URLs for 24h
- [ ] API authentication works
- [ ] All existing tests still pass
- [ ] New tests for API endpoints

## Related Documentation

- AGENTS.md "Task Object and Plan Architecture"
- DOWN_AND_UP/terminal_outcome_result.py
- .ai/tasks/20260330-002-migration-completed-decisions.md
