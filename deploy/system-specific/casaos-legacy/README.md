# CasaOS Legacy Deployment Guide

> For older CasaOS versions (0.4.x and earlier) on ZimaBoard and similar devices

## Overview

Older CasaOS versions have limited functionality compared to newer releases:
- ❌ No reliable folder upload in Files app
- ❌ No "Import" button in Custom Install (Docker Compose import)
- ❌ SSH may be unreliable or disabled
- ❌ No built-in terminal app
- ✅ Web UI file manager (Files app) works for individual files
- ✅ Custom app installation via form fields

## Prerequisites

- ZimaBoard or similar device running CasaOS v0.4.x
- Access to CasaOS web UI at `http://your-zima-ip` (e.g., `http://192.168.1.210`)
- Your config files ready locally

## Deployment Steps

### Step 1: Prepare Files Locally

On your computer, ensure you have:
- `config.py` - Your bot configuration
- `cookie.txt` - YouTube cookies (Netscape format)
- Additional cookie files (optional)

### Step 2: Create Folder Structure via Files App

1. Open CasaOS web UI → **Files** app
2. Navigate to `/DATA`
3. Create folder: `AppData`
4. Inside `AppData`, create: `tg-ytdlp-bot`
5. Inside `tg-ytdlp-bot`, create:
   - `CONFIG/`
   - `TXT/`

Final structure:
```
/DATA/AppData/tg-ytdlp-bot/
├── CONFIG/
└── TXT/
```

### Step 3: Upload Config Files

Use **"Upload or create" → "Upload files"** (upload files one by one):

| Upload This File | To This Location |
|------------------|------------------|
| `config.py` | `/DATA/AppData/tg-ytdlp-bot/CONFIG/config.py` |
| `cookie.txt` | `/DATA/AppData/tg-ytdlp-bot/TXT/cookie.txt` |

### Step 4: Uninstall Old Version

1. Go to CasaOS dashboard
2. Find existing tg-ytdlp-bot app
3. Click **"Turn-off"** (stop the app)
4. Click **"Uninstall"**

### Step 5: Install New Version

1. Click **"+"** (Add app)
2. Select **"Install a customized app"**
3. Fill in the form using values from `casaos-form-values.yaml` in this folder

### Step 6: Verify

1. App should appear on dashboard
2. Wait 1-2 minutes for initialization
3. Click **"Launch and Open"**
4. Dashboard should be accessible at `http://your-zima-ip:5555`

## Troubleshooting

### "App may not be available" error
- Wait 1-2 minutes after installation (Docker image is downloading)
- Check container logs if available
- Ensure port 5555 is not in use by another app

### Config not loading
- Verify file paths in volume mounts match your uploaded files
- Ensure `config.py` syntax is valid

### Cookie errors
- Verify `cookie.txt` is in Netscape format
- Check cookie file is uploaded to correct location

## Known Limitations

1. **No multi-container support**: Old CasaOS Custom Install typically supports single containers. This deployment combines services or you may need to install additional services (like Caddy for cookies) separately via App Store.

2. **No build from Dockerfile**: Must use pre-built image or install dependencies manually.

3. **Manual file uploads only**: Cannot upload folders; files must be uploaded individually.

## Alternative: Docker Compose via Command Line

If you gain SSH access later, you can use the standard deployment:

```bash
cd /DATA/AppData/tg-ytdlp-bot
docker compose up -d
```

## References

- [CasaOS Documentation](https://www.zimaspace.com/docs/)
- [ZimaBoard Community Forum](https://community.zimaspace.com/)
