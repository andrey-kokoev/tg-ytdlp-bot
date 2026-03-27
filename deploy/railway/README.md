# Railway Deployment Guide

> Deploy tg-ytdlp-bot to Railway.app - Managed cloud hosting with free tier

## Overview

[Railway](https://railway.app) is a managed Platform-as-a-Service (PaaS) that makes deploying Docker containers easy.

**Pros:**
- ✅ No server management needed
- ✅ Automatic HTTPS/SSL
- ✅ Git-based deployments
- ✅ Managed databases available
- ✅ Free tier available
- ✅ Easy environment variables

**Cons:**
- ⚠️ Multi-service setup required (3 separate services)
- ⚠️ Requires Dockerfile (no native compose support)
- ⚠️ Persistent storage limitations (ephemeral filesystem)
- ⚠️ Cost for sustained usage (free tier has limits)

## Prerequisites

- Railway account: [signup](https://railway.app)
- GitHub account (for repo connection)
- Your `config.py` and `cookie.txt` files ready
- Railway CLI (optional but recommended): `npm i -g @railway/cli`

## Deployment Options

### Option A: One-Click Deploy (Template)

*(Community template - not yet available)*

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template-here)

### Option B: Manual Multi-Service Setup (Recommended)

Railway doesn't support `docker-compose.yml` directly. You need to deploy **3 services** separately.

---

## Step-by-Step Deployment

### Step 1: Fork/Clone the Repository

```bash
# Fork the repo on GitHub first, then clone your fork
git clone https://github.com/YOUR_USERNAME/tg-ytdlp-bot.git
cd tg-ytdlp-bot
```

### Step 2: Modify for Railway

Railway needs a combined single-service approach. Create `railway.Dockerfile`:

```dockerfile
FROM python:3.10-slim

ARG TZ=Europe/Moscow
ENV TZ="$TZ"

# Install all system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    mediainfo \
    rsync \
    fonts-noto-core \
    fonts-noto-extra \
    fonts-kacst-one \
    fonts-noto-cjk \
    fonts-indic \
    fonts-noto-color-emoji \
    fontconfig \
    libass9 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Amiri Arabic font
RUN git clone https://github.com/aliftype/amiri.git /tmp/amiri \
    && mkdir -p /usr/share/fonts/truetype/amiri \
    && cp /tmp/amiri/fonts/*.ttf /usr/share/fonts/truetype/amiri/ \
    && fc-cache -fv \
    && rm -rf /tmp/amiri

WORKDIR /app

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire app
COPY . .

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Railway uses PORT env variable
ENV PORT=5555

# Start command
CMD ["bash", "docker-entrypoint.sh"]
```

Create `railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "railway.Dockerfile"
  },
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Step 3: Configure Environment Variables

Create a `.env.example` file (don't commit secrets):

```
COMPOSE_PROJECT_NAME=tg-ytdlp-bot
TZ=America/Chicago
PYTHONUNBUFFERED=1

# Note: Real config goes in CONFIG/config.py
# Railway environment variables are for runtime only
```

### Step 4: Create Railway Project

**Via Web UI:**

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your forked tg-ytdlp-bot repo
5. Railway will auto-detect the Dockerfile

**Via CLI:**

```bash
# Login
railway login

# Create project and link
railway init

# Link to existing project
railway link
```

### Step 5: Add Environment Variables

In Railway Dashboard:

1. Go to your project
2. Click on the **tg-ytdlp-bot service**
3. Go to **Variables** tab
4. Add:

| Variable | Value |
|----------|-------|
| `COMPOSE_PROJECT_NAME` | `tg-ytdlp-bot` |
| `TZ` | `America/Chicago` |
| `PYTHONUNBUFFERED` | `1` |
| `PORT` | `5555` |

**Note:** Config secrets (API keys, bot token) go in `CONFIG/config.py`, not Railway env vars.

### Step 6: Configure Persistent Storage

Railway filesystem is ephemeral - data is lost on redeploy. For persistent data:

1. In Railway Dashboard, go to **Settings**
2. Scroll to **Volume Mounts**
3. Add volume:
   - Mount Path: `/app/users`
   - Size: 10GB (adjust as needed)

Repeat for:
- `/app/CONFIG` (for config persistence)
- `/app/TXT` (for cookies)

**Alternative:** Use Railway's managed Postgres for user data (requires code changes).

### Step 7: Deploy

**Via Web:**
1. Click **"Deploy"** in Railway dashboard
2. Wait for build (~5-10 minutes)
3. Check logs for errors

**Via CLI:**
```bash
railway up
```

### Step 8: Configure Networking

1. In Railway Dashboard, click your service
2. Go to **Settings** → **Networking**
3. Click **Generate Domain** (for public access)
4. Or set custom domain

**Note:** Bot works without public domain (Telegram Bot API sends messages directly).

### Step 9: Upload Config Files

Since Railway filesystem is ephemeral for source files, you have options:

**Option A: Config in Git (Not Recommended for Secrets)**
```bash
# Create config in repo (risky - config contains secrets!)
git add CONFIG/config.py
```

**Option B: Railway Volume (Recommended)**
```bash
# Use Railway CLI to upload files to volume
# Or use Railway's "Volume" feature to mount persistent storage
```

**Option C: Environment Variables Override** (requires code modification)
Modify bot to read config from env vars instead of config.py.

### Step 10: Test

1. Check Railway logs: `railway logs` or Dashboard → Logs
2. Message your bot on Telegram
3. Test dashboard: Visit the generated Railway domain

---

## Multi-Service Setup (Full Features)

For full functionality (PO tokens, cookie webserver), deploy 3 services:

### Service 1: bgutil-provider

1. In Railway, click **"New"** → **"Database"** (not needed, just for UI) or **"Empty Service"**
2. Use image: `brainicism/bgutil-ytdlp-pot-provider`
3. Environment:
   - `SERVER_PORT=4416`
4. Networking: Private (no public domain needed)

### Service 2: configuration-webserver

1. New service
2. Use image: `caddy:2-alpine`
3. Mount volume with cookie files
4. Private networking

### Service 3: tg-ytdlp-bot (Main)

1. Deploy from your GitHub repo (Dockerfile)
2. Set environment variable:
   - `YOUTUBE_POT_BASE_URL=http://bgutil-provider:4416`
3. Connect to other services via Railway's private networking

**Note:** Railway charges per service, so 3 services = 3x cost.

---

## Free Tier Limits

| Resource | Free Tier |
|----------|-----------|
| Execution time | 500 hours/month |
| RAM | 512MB per service |
| Disk | 1GB ephemeral |
| Egress | 100GB/month |
| Services | Unlimited (but hours shared) |

**Tips to stay free:**
- Deploy single service (skip PO provider, use public one)
- Use external cookie server
- Keep bot lightweight

---

## Cost Estimation

If free tier isn't enough:

| Setup | Monthly Cost |
|-------|--------------|
| Single service (minimal) | $5-10 |
| Full 3-service setup | $15-30 |
| With volumes (persistent storage) | +$5-10 |

---

## Troubleshooting

### Build fails
```bash
# Check Railway build logs
# Common issues:
# - Missing system packages (ffmpeg, etc.)
# - Git clone timeout (Amiri fonts)
```

### Container crashes
```bash
# Check logs
railway logs

# Common issues:
# - Missing config.py
# - Invalid cookie file
# - Port conflict
```

### Dashboard not accessible
```bash
# Ensure PORT env var matches exposed port
# Railway requires PORT to be set
```

### Data lost on redeploy
```bash
# You didn't configure volumes!
# Go to Railway Dashboard → Service → Settings → Volume Mounts
```

---

## Alternative: Railway + External Services

To reduce costs, use Railway only for the main bot:

| Service | Provider | Cost |
|---------|----------|------|
| Main bot (tg-ytdlp-bot) | Railway | Free tier |
| PO Token Provider | Self-hosted or skip | $0 |
| Cookie webserver | Public HTTPS URL | $0 |

---

## Migration from ZimaBoard to Railway

1. Export config: `tar czf config-backup.tar.gz CONFIG/ TXT/`
2. Setup Railway project
3. Upload config to Railway volume
4. Update webhook URL if using webhooks
5. Test thoroughly before shutting down ZimaBoard

---

## Resources

- [Railway Documentation](https://docs.railway.app/)
- [Railway Pricing](https://railway.app/pricing)
- [Dockerfile Best Practices](https://docs.docker.com/develop/dev-best-practices/dockerfile_best-practices/)
