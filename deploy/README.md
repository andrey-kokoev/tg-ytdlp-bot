# Deployment Options for tg-ytdlp-bot

This folder contains deployment guides and configurations for various platforms.

## Quick Reference

| Platform | Folder | Difficulty | Cost | Best For |
|----------|--------|------------|------|----------|
| **New ZimaBoard** (ZimaOS) | [`zimaboard-new/`](zimaboard-new/) | ⭐ Easy | One-time | Home server, self-hosted |
| **Railway** (Cloud) | [`railway/`](railway/) | ⭐⭐ Medium | Free tier + usage | Managed hosting, no maintenance |
| **Old ZimaBoard** (CasaOS 0.4.x) | [`system-specific/casaos-legacy/`](system-specific/casaos-legacy/) | ⭐⭐⭐ Hard | One-time | Legacy hardware only |
| **Generic VPS/Server** | See main [README.md](../README.md) | ⭐⭐ Medium | Monthly | Full control, any provider |

## Recommended Deployment

### For New Users: New ZimaBoard + ZimaOS

The easiest self-hosted option with full Docker Compose support.

```bash
# On ZimaBoard with ZimaOS
mkdir -p /DATA/AppData/tg-ytdlp-bot
cd /DATA/AppData/tg-ytdlp-bot

# Download compose file
curl -fsSL https://raw.githubusercontent.com/chelaxian/tg-ytdlp-bot/main/docker-compose.yml -o docker-compose.yml

# Start
docker compose up -d
```

See [`zimaboard-new/`](zimaboard-new/) for full guide.

### For Cloud Hosting: Railway

Managed hosting with automatic deployments.

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

See [`railway/`](railway/) for full guide.

## Platform Comparison

### New ZimaBoard (Recommended for Self-Hosting)

**Pros:**
- One-time cost (~$120-200)
- Full Docker Compose support
- Built-in terminal
- Local storage (no egress costs)
- Works offline

**Cons:**
- Initial hardware cost
- Home network dependent
- You manage updates

### Railway (Recommended for Cloud)

**Pros:**
- No server management
- Free tier available
- Git-based deployments
- Automatic HTTPS

**Cons:**
- Monthly costs for sustained usage
- Multi-service complexity
- Ephemeral filesystem (volumes needed)

### Legacy CasaOS (Avoid if Possible)

Only use if you have old ZimaBoard with CasaOS 0.4.x and cannot upgrade.

See [`system-specific/casaos-legacy/`](system-specific/casaos-legacy/).

## Generic VPS Deployment

For any Linux VPS (DigitalOcean, Linode, AWS, etc.):

```bash
# Standard Docker Compose deployment
git clone https://github.com/chelaxian/tg-ytdlp-bot.git
cd tg-ytdlp-bot
cp CONFIG/_config.py CONFIG/config.py
# Edit CONFIG/config.py with your settings
docker compose up -d --build
```

See main repository [README.md](../README.md) for details.

## Contributing

Have a new deployment method? Add it here!

1. Create new folder: `deploy/your-platform/`
2. Include:
   - `README.md` - Step-by-step guide
   - Any config files (Dockerfile, compose overrides, etc.)
   - Troubleshooting section
3. Update this README
4. Submit PR

## Support

- Main repo: [chelaxian/tg-ytdlp-bot](https://github.com/chelaxian/tg-ytdlp-bot)
- Issues: [GitHub Issues](https://github.com/chelaxian/tg-ytdlp-bot/issues)
- Community: [Telegram @tg_ytdlp](https://t.me/tg_ytdlp)
