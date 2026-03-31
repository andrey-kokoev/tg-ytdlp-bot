# Task: Cloudflare Tunnel Setup for HTTP API Access

## Metadata
- **Status**: 🚧 In Progress
- **Priority**: HIGH
- **Created**: 2026-03-30
- **Category**: Infrastructure / Deployment

## Summary

Set up Cloudflare Tunnel to expose bot's HTTP API (port 5555) to Cloudflare Workers without opening firewall ports or needing public IP.

## Architecture

```
Cloudflare Worker → bot-api.yourdomain.com → Cloudflare Edge → Tunnel → ZimaBoard:5555
```

## Prerequisites

- [ ] Domain managed by Cloudflare
- [ ] ZimaBoard running the bot
- [ ] Docker Compose setup (existing)

## Implementation Steps

### 1. Install cloudflared (Docker)

Add to `docker-compose.yml`:

```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: cloudflared
    command: tunnel run --token ${TUNNEL_TOKEN}
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN}
    restart: unless-stopped
    networks:
      - bot-network
    # No ports exposed - tunnel is outbound only
```

### 2. Configure Environment

Add to `.env`:
```bash
# Cloudflare Tunnel (get from: cloudflared tunnel token <tunnel-name>)
TUNNEL_TOKEN=<your-tunnel-token>
```

Add to `.env.example`:
```bash
# Cloudflare Tunnel Token
# Create tunnel: cloudflared tunnel create bot-api
# Get token: cloudflared tunnel token bot-api
TUNNEL_TOKEN=
```

### 3. DNS Configuration

In Cloudflare dashboard:
1. Create CNAME record:
   - Name: `bot-api` (or subdomain of choice)
   - Target: `<TUNNEL_ID>.cfargotunnel.com`
   - Proxy status: Proxied (orange cloud)

### 4. Tunnel Configuration

Option A: Via Cloudflare Dashboard (recommended)
- Create tunnel in Zero Trust dashboard
- Add public hostname: `bot-api.yourdomain.com` → `http://app:5555`
- Copy token to `.env`

Option B: Via config file
Create `docker/cloudflared/config.yml`:
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /etc/cloudflared/credentials.json

ingress:
  - hostname: bot-api.yourdomain.com
    service: http://app:5555
    originRequest:
      noTLSVerify: true  # If using self-signed cert internally
  - service: http_status:404
```

### 5. Update docker-compose.yml

Ensure `cloudflared` and `app` services share network:

```yaml
services:
  app:
    # ... existing config
    networks:
      - bot-network
    ports:
      # Keep internal, not exposed to host internet
      - "127.0.0.1:5555:5555"  # Only localhost, not 0.0.0.0
    
  cloudflared:
    # ... config above
    networks:
      - bot-network

networks:
  bot-network:
    driver: bridge
```

### 6. Verify Setup

```bash
# Start services
docker compose up -d cloudflared

# Check tunnel status
docker logs cloudflared

# Test from outside (or Cloudflare Worker)
curl https://bot-api.yourdomain.com/health
```

## Security Configuration

### API Authentication

The HTTP API should validate requests. Options:

**Option A: API Key in Header**
```python
# web/api_jobs.py
async def verify_api_key(request: Request):
    api_key = request.headers.get("X-API-Key")
    if api_key not in Config.ALLOWED_API_KEYS:
        raise HTTPException(status_code=401)
```

**Option B: Cloudflare Access (Zero Trust)**
- Enable Cloudflare Access on `bot-api.yourdomain.com`
- Require Service Token authentication
- Worker includes token in requests

**Option C: HMAC Signature**
```python
# Verify request signature
expected_sig = hmac_sha256(payload, shared_secret)
if not hmac.compare_digest(expected_sig, request.headers["X-Signature"]):
    raise HTTPException(status_code=401)
```

**Recommendation**: Start with Option A (API Key), migrate to C (HMAC) if needed.

## Cloudflare Worker Example

```javascript
// worker.js
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    if (url.pathname === '/submit-download') {
      // Call bot API through tunnel
      const response = await fetch('https://bot-api.yourdomain.com/api/jobs', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.BOT_API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          url: request.url,
          callback_url: `${env.WORKER_URL}/webhook`
        })
      });
      
      return new Response(JSON.stringify(await response.json()), {
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Webhook handler
    if (url.pathname === '/webhook') {
      const result = await request.json();
      // Process completed download
      await env.KV.put(`job:${result.job_id}`, JSON.stringify(result));
      return new Response('OK');
    }
    
    return new Response('Not Found', { status: 404 });
  }
};
```

## Environment Variables

Add to bot `CONFIG/config.py`:
```python
# API Authentication
API_KEYS = os.getenv("API_KEYS", "").split(",")  # Comma-separated keys
FILE_SERVE_SECRET = os.getenv("FILE_SERVE_SECRET", "change-me")
FILE_SERVE_EXPIRY_HOURS = int(os.getenv("FILE_SERVE_EXPIRY_HOURS", "24"))
```

## Testing

1. **Tunnel connectivity:**
```bash
curl https://bot-api.yourdomain.com/health
# Should return: {"status": "ok"}
```

2. **Job submission:**
```bash
curl -X POST https://bot-api.yourdomain.com/api/jobs \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video", "callback_url": "https://httpbin.org/post"}'
```

3. **Webhook received:**
Check httpbin or your worker logs for callback.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Tunnel shows "connected" but 404 | Check ingress rule matches hostname exactly |
| Connection timeout | Verify `app:5555` is reachable from cloudflared container |
| SSL errors | Set `noTLSVerify: true` in originRequest or use proper cert |
| 502 Bad Gateway | Bot service not running on port 5555 |

## Files to Create/Modify

**Modify:**
- `docker-compose.yml` - Add cloudflared service
- `.env` - Add TUNNEL_TOKEN
- `.env.example` - Document required vars
- `CONFIG/config.py` - Add API auth settings

**Create:**
- `docker/cloudflared/config.yml` (if using file-based config)

## References

- Cloudflare Tunnel docs: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
- Docker image: https://hub.docker.com/r/cloudflare/cloudflared

## Acceptance Criteria

- [ ] cloudflared service runs in Docker
- [ ] HTTPS accessible via bot-api.yourdomain.com
- [ ] No firewall ports opened (outbound tunnel only)
- [ ] API authentication working
- [ ] Cloudflare Worker can submit jobs
- [ ] Webhook callbacks received by Worker
