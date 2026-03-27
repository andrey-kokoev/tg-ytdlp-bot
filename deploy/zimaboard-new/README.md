# New ZimaBoard Deployment Guide

> For ZimaBoard 2 and newer ZimaOS (v1.0+) with full Docker Compose support

## Overview

Newer ZimaBoards run **ZimaOS** (successor to CasaOS) which includes:
- ✅ Full Docker Compose support
- ✅ Built-in terminal (web-based)
- ✅ SSH enabled by default
- ✅ Better file management
- ✅ Multi-container app support

## Prerequisites

- ZimaBoard 2 or newer (or ZimaBoard 1 with ZimaOS flashed)
- ZimaOS v1.0+ installed
- Network access (ethernet recommended)
- Your config files ready

## Method 1: Web Terminal (Easiest)

### Step 1: Access ZimaOS

1. Power on your ZimaBoard
2. Find its IP address (check router or use `zima.local`)
3. Open browser: `http://your-zima-ip`
4. Login with your ZimaOS credentials

### Step 2: Open Terminal

1. In ZimaOS dashboard, click **"Terminal"** or **">_"** icon
2. This opens a web-based terminal with root access

### Step 3: Install tg-ytdlp-bot

In the web terminal, run:

```bash
# Create app directory
mkdir -p /DATA/AppData/tg-ytdlp-bot
cd /DATA/AppData/tg-ytdlp-bot

# Download docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/chelaxian/tg-ytdlp-bot/main/docker-compose.yml -o docker-compose.yml

# Download entrypoint script
curl -fsSL https://raw.githubusercontent.com/chelaxian/tg-ytdlp-bot/main/docker-entrypoint.sh -o docker-entrypoint.sh
chmod +x docker-entrypoint.sh

# Download requirements (optional, for reference)
curl -fsSL https://raw.githubusercontent.com/chelaxian/tg-ytdlp-bot/main/requirements.txt -o requirements.txt

# Create directory structure
mkdir -p CONFIG TXT docker/configuration-webserver/site/cookies
```

### Step 4: Upload Config Files

1. In ZimaOS, open **Files** app
2. Navigate to `/DATA/AppData/tg-ytdlp-bot/`
3. Upload your files:
   - `CONFIG/config.py` → `CONFIG/`
   - `TXT/cookie.txt` → `TXT/`

### Step 5: Start the Bot

Back in the terminal:

```bash
cd /DATA/AppData/tg-ytdlp-bot

# Pull and build images
docker compose pull
docker compose up -d --build

# Check status
docker compose ps

# View logs
docker compose logs -f app
```

### Step 6: Access Dashboard

- Dashboard: `http://your-zima-ip:5555`
- Default login: `admin` / `admin123`

---

## Method 2: SSH (Alternative)

If you prefer SSH over web terminal:

```bash
# SSH into ZimaBoard (default credentials for new setup)
ssh root@your-zima-ip
# OR
ssh casaos@your-zima-ip

# Then follow Step 3-5 from Method 1
```

Default credentials (change these!):
- Username: `root` or `casaos`
- Password: `casaos`

---

## Method 3: ZimaOS App Store (Future)

If someone creates a ZimaOS app template:

1. Open ZimaOS App Store
2. Search for "tg-ytdlp-bot"
3. Click Install
4. Configure via UI

*(Not currently available - community contribution welcome!)*

---

## Directory Structure

```
/DATA/AppData/tg-ytdlp-bot/
├── docker-compose.yml
├── docker-entrypoint.sh
├── CONFIG/
│   └── config.py          # Your bot config
├── TXT/
│   └── cookie.txt         # YouTube cookies
├── docker/
│   └── configuration-webserver/
│       └── site/
│           └── cookies/   # Additional cookies
└── users/                 # User data (auto-created)
```

---

## Updating

To update to latest version:

```bash
cd /DATA/AppData/tg-ytdlp-bot

# Pull latest images
docker compose pull

# Rebuild and restart
docker compose up -d --build

# Check logs
docker compose logs -f app
```

---

## Troubleshooting

### Port 5555 already in use
```bash
# Check what's using port 5555
sudo lsof -i :5555

# Change port in docker-compose.yml if needed
# Edit the port mapping: "5556:5555" instead of "5555:5555"
```

### Container won't start
```bash
# Check logs
docker compose logs app

# Check disk space
df -h

# Restart services
docker compose restart
```

### Permission denied
```bash
# Fix permissions
sudo chown -R $(whoami):$(whoami) /DATA/AppData/tg-ytdlp-bot
```

---

## Useful Commands

```bash
# View all containers
docker ps

# Stop bot
docker compose down

# Restart bot
docker compose restart

# Update just the app (faster)
docker compose up -d --build app

# Backup config
tar czf ~/tg-ytdlp-bot-backup-$(date +%Y%m%d).tar.gz CONFIG/ TXT/
```

---

## Advantages Over Old CasaOS

| Feature | Old CasaOS (0.4.x) | New ZimaOS (1.0+) |
|---------|-------------------|-------------------|
| Docker Compose | ❌ Not supported | ✅ Full support |
| Multi-container | ❌ Single only | ✅ Full support |
| Terminal | ❌ Not available | ✅ Built-in web terminal |
| SSH | ⚠️ Unreliable | ✅ Enabled by default |
| File upload | ❌ Single files only | ✅ Folders + drag-drop |
| Updates | ❌ Manual | ✅ Built-in updater |

---

## Resources

- [ZimaOS Documentation](https://www.zimaspace.com/docs/zimaos/)
- [ZimaBoard Community](https://community.zimaspace.com/)
- Main repo: [tg-ytdlp-bot](https://github.com/chelaxian/tg-ytdlp-bot)
