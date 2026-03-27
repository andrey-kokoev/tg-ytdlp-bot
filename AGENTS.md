# AGENTS.md - AI Coding Agent Guide for tg-ytdlp-bot

> This file contains essential information for AI coding agents working on this project.
> Read this before making any changes to understand the architecture, conventions, and development workflow.

---

## Project Overview

**tg-ytdlp-bot** is an advanced Telegram bot for downloading videos, audio, and images from 1500+ platforms (YouTube, TikTok, Instagram, Twitter/X, Facebook, etc.) using yt-dlp and gallery-dl.

### Key Features
- Multi-language support (English, Russian, Arabic, Hindi)
- Interactive quality selection menus
- Cookie-based authentication for private content
- Proxy support with automatic failover
- PO Token Provider for YouTube anti-bot bypass
- Web dashboard for monitoring and administration
- NSFW content detection and filtering
- Rate limiting and flood protection
- Group/channel support with admin controls

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| Telegram API | PyroTGFork (Pyrogram fork) |
| Video Download | yt-dlp |
| Image Download | gallery-dl |
| Web Dashboard | FastAPI + Jinja2 + Uvicorn |
| HTTP Client | aiohttp, requests |
| Video Processing | ffmpeg, moviepy |
| Containerization | Docker + Docker Compose |
| Testing | pytest |

---

## Project Structure

```
tg-ytdlp-bot/
├── magic.py                    # Main entry point, app initialization
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker image definition
├── docker-compose.yml          # Multi-service orchestration
├── docker-entrypoint.sh        # Container startup script
│
├── CONFIG/                     # Configuration modules
│   ├── config.py               # Main configuration class
│   ├── _config.py              # Template for config.py
│   ├── config_secret.py        # Secrets (API keys, tokens) - gitignored
│   ├── config_secret.example.py # Template for secrets
│   ├── commands.py             # Command definitions
│   ├── messages.py             # Message loading system
│   ├── limits.py               # Rate limits and restrictions
│   ├── domains.py              # Domain lists (blacklist, whitelist, etc.)
│   └── LANGUAGES/              # Translation files
│       ├── language_router.py  # Language detection and routing
│       ├── messages_EN.py      # English
│       ├── messages_RU.py      # Russian
│       ├── messages_AR.py      # Arabic
│       └── messages_IN.py      # Hindi
│
├── COMMANDS/                   # Bot command handlers
│   ├── admin_cmd.py            # Admin commands (/block, /ban, etc.)
│   ├── args_cmd.py             # /args command
│   ├── clean_cmd.py            # /clean command
│   ├── cookies_cmd.py          # Cookie management
│   ├── format_cmd.py           # Format selection
│   ├── image_cmd.py            # /img for image galleries
│   ├── lang_cmd.py             # Language switching
│   ├── link_cmd.py             # Direct link generation
│   ├── list_cmd.py             # Playlist listing
│   ├── mediainfo_cmd.py        # Media information
│   ├── nsfw_cmd.py             # NSFW settings
│   ├── other_handlers.py       # start, help, text handlers
│   ├── proxy_cmd.py            # Proxy configuration
│   ├── search.py               # Video search
│   ├── settings_cmd.py         # User settings
│   ├── split_sizer.py          # Video splitting
│   ├── subtitles_cmd.py        # Subtitle handling
│   └── tag_cmd.py              # Tag management
│
├── HELPERS/                    # Utility modules
│   ├── app_instance.py         # Global app instance management
│   ├── caption.py              # Caption formatting
│   ├── channel_guard.py        # Channel subscription checking
│   ├── decorators.py           # Pyrogram decorators
│   ├── download_status.py      # Download progress tracking
│   ├── filesystem_hlp.py       # File system utilities
│   ├── limitter.py             # Rate limiting
│   ├── logger.py               # Logging utilities
│   ├── porn.py                 # NSFW detection
│   ├── proxy_helper.py         # Proxy management
│   ├── qualifier.py            # URL qualification
│   ├── safe_messeger.py        # Safe message sending
│   └── text_helper.py          # Text processing
│
├── URL_PARSERS/                # URL processing
│   ├── engine_router.py        # Download engine selection
│   ├── filter_check.py         # Domain filtering
│   ├── normalizer.py           # URL normalization
│   ├── playlist_utils.py       # Playlist handling
│   ├── tags.py                 # Tag extraction
│   ├── thumbnail_downloader.py # Thumbnail handling
│   ├── tiktok.py               # TikTok-specific logic
│   ├── url_extractor.py        # Main URL dispatcher
│   ├── video_extractor.py      # Video info extraction
│   └── youtube.py              # YouTube-specific logic
│
├── DOWN_AND_UP/                # Download and upload logic
│   ├── always_ask_menu.py      # Interactive quality menu
│   ├── down_and_audio.py       # Audio download logic
│   ├── down_and_up.py          # Main download/upload flow
│   ├── ffmpeg.py               # FFmpeg operations
│   ├── gallery_dl_hook.py      # gallery-dl integration
│   ├── live_stream_downloader.py # Live stream handling
│   ├── sender.py               # Telegram upload logic
│   └── yt_dlp_hook.py          # yt-dlp integration
│
├── DATABASE/                   # Database layer
│   ├── cache_db.py             # Firebase cache operations
│   ├── download_firebase.py    # Firebase download script
│   └── firebase_init.py        # Firebase initialization
│
├── services/                   # Dashboard services
│   ├── auth_service.py         # Dashboard authentication
│   ├── lists_service.py        # List management
│   ├── stats_collector.py      # Statistics collection
│   ├── stats_events.py         # Stats event handling
│   ├── stats_service.py        # Stats API service
│   └── system_service.py       # System management
│
├── web/                        # Web dashboard
│   ├── dashboard_app.py        # FastAPI application
│   ├── static/                 # Static assets (CSS, JS)
│   └── templates/              # Jinja2 templates
│
├── PATCH/                      # Runtime patches
│   ├── GLOBAL_MESSAGES_PATCH.py
│   └── FIX_NONE_COMPARISONS_PATCH.py
│
├── docs/                       # Documentation
│   ├── getting-started/
│   ├── configuration/
│   ├── commands/
│   ├── advanced/
│   └── development/
│
├── tests/                      # Test suite
│   └── test_stats_collector.py
│
├── TXT/                        # Data files
│   ├── cookie.txt              # Default cookies
│   ├── porn_domains.txt        # NSFW domain list
│   └── porn_keywords.txt       # NSFW keyword list
│
└── docker/                     # Docker configuration
    └── configuration-webserver/
        ├── conf/               # Caddy config
        └── site/cookies/       # Cookie files
```

---

## Build and Run Commands

### Docker Deployment (Recommended)

```bash
# Build and start all services
docker compose up -d --build

# View logs
docker compose logs -f app

# Stop all services
docker compose down

# Restart specific service
docker compose restart app
```

### Manual Development Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the bot
python magic.py

# Run with dashboard (separate terminal)
python -m uvicorn web.dashboard_app:app --host 0.0.0.0 --port 5555
```

---

## Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_stats_collector.py -v

# Run with coverage
pytest --cov=. --cov-report=html
```

---

## Code Style Guidelines

- **Follow PEP 8**: Use 4 spaces for indentation, limit lines to 100 characters
- **Imports order**: stdlib → third-party → local modules
- **Docstrings**: Use triple quotes for module, class, and function documentation
- **Type hints**: Use typing annotations where applicable
- **Error handling**: Use try/except with specific exceptions, log errors properly
- **Logging**: Use the `HELPERS.logger` module for all logging

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Constants | UPPER_SNAKE_CASE | `MAX_FILE_SIZE_GB` |
| Classes | PascalCase | `StatsCollector` |
| Functions/Methods | snake_case | `download_video()` |
| Variables | snake_case | `user_id` |
| Private | _leading_underscore | `_validate_config()` |

---

## Configuration System

The bot uses a layered configuration approach:

1. **CONFIG/config.py**: Main configuration (edit this)
2. **CONFIG/config_secret.py**: Secrets override (API_ID, API_HASH, BOT_TOKEN) - gitignored
3. **CONFIG/_config.py**: Template for creating config.py

### Key Configuration Sections

```python
# Required settings
BOT_NAME = "your_bot_name"
BOT_NAME_FOR_USERS = "username_in_db"
ADMIN = [123456789]  # Admin user IDs
API_ID = 12345678
API_HASH = "your_api_hash"
BOT_TOKEN = "your:bot_token"

# Log channels (can use same channel for all)
LOGS_ID = -1001234567890
LOGS_VIDEO_ID = -1001234567890
LOGS_NSFW_ID = -1001234567890
LOG_EXCEPTION = -1001234567890

# Subscription gating
SUBSCRIBE_CHANNEL = -1001234567890
SUBSCRIBE_CHANNEL_URL = "https://t.me/your_channel"
REQUIRED_CHANNEL_MENTION = "@your_channel"

# Dashboard
DASHBOARD_PORT = 5555
DASHBOARD_USERNAME = "admin"
DASHBOARD_PASSWORD = "change_me"  # Change immediately!
```

---

## Module Architecture

### Import Order in magic.py

The main file follows a strict import order to avoid circular dependencies:

1. Global patches (PATCH modules)
2. Standard library imports
3. Third-party imports (Pyrogram, yt-dlp)
4. CONFIG modules (config, messages)
5. Validation functions
6. HELPERS (without handlers)
7. App initialization (Pyrogram Client)
8. DATABASE modules
9. URL_PARSERS modules
10. DOWN_AND_UP modules
11. HELPERS (with handlers)
12. COMMANDS modules

### Handler Registration

Command handlers are registered via decorators in their respective modules. The `magic.py` file imports these modules to trigger the decorator execution.

### Group Support

Group commands are wrapped with `_wrap_group()` to ensure only allowed groups (defined in `ALLOWED_GROUP` config) can use the bot.

---

## Database and Caching

### Firebase Integration

- **Primary storage**: Firebase Realtime Database (optional, can run locally)
- **Cache file**: `dump.json` - local cache of Firebase data
- **Auto-reload**: Cache automatically reloads every hour
- **Offline mode**: Set `USE_FIREBASE = False` to run without Firebase

### Local Storage

- `users/`: User-specific data (cookies, settings)
- `DATABASE/`: Firebase integration scripts
- `TXT/`: Data files (cookies, domain lists)

---

## Security Considerations

### Secrets Management

- NEVER commit `CONFIG/config_secret.py`
- Use environment variables or secret management for production
- Cookie files should not be committed to git

### Rate Limiting

- Per-minute, per-hour, per-day URL limits
- Command spam protection
- Group multiplier for relaxed limits in groups

### NSFW Handling

- Domain-based and keyword-based detection
- Separate logging channels for NSFW content
- User toggle for NSFW content blocking

### Cookie Security

- Cookies served via internal webserver (not exposed publicly)
- Multiple cookie sources with automatic failover
- Cookie validation before use

---

## Docker Services

The `docker-compose.yml` defines 3 services:

| Service | Image | Purpose |
|---------|-------|---------|
| app | Built from Dockerfile | Main bot application |
| bgutil-provider | brainicism/bgutil-ytdlp-pot-provider | YouTube PO token provider |
| configuration-webserver | caddy:2-alpine | Serves cookie files internally |

---

## Language Support

The bot supports 4 languages with a dynamic loading system:

1. **English** (EN) - default
2. **Russian** (RU)
3. **Arabic** (AR)
4. **Hindi** (IN)

Messages are loaded from `CONFIG/LANGUAGES/messages_XX.py` files via the `language_router.py` module.

---

## Common Development Tasks

### Adding a New Command

1. Create handler in appropriate `COMMANDS/` module
2. Add command definition in `CONFIG/commands.py`
3. Add translations in `CONFIG/LANGUAGES/messages_XX.py`
4. Import module in `magic.py` after app initialization
5. Add group handler if command should work in groups

### Adding a New Language

1. Create `CONFIG/LANGUAGES/messages_XX.py` (copy from EN)
2. Update `CONFIG/LANGUAGES/language_router.py` with new language
3. Add language option in settings command

### Modifying Download Logic

- yt-dlp integration: `DOWN_AND_UP/yt_dlp_hook.py`
- gallery-dl integration: `DOWN_AND_UP/gallery_dl_hook.py`
- Quality selection: `DOWN_AND_UP/always_ask_menu.py`
- Upload logic: `DOWN_AND_UP/sender.py`

---

## Troubleshooting

### Common Issues

1. **Session lock errors**: Delete `magic.session-lock` file
2. **Firebase connection errors**: Check `USE_FIREBASE` setting and credentials
3. **Cookie errors**: Verify cookie file format (Netscape) and accessibility
4. **Flood wait errors**: Rate limits triggered, wait before retrying

### Log Files

- `bot.log`: Main application log
- Check log channels in Telegram for errors

---

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes, commit
git add .
git commit -m "feat: add new feature"

# Push and create PR
git push origin feature/my-feature
```

### Files to Never Commit

- `CONFIG/config_secret.py`
- `magic.session*` (session files)
- `dump.json` (cache)
- `bot.log` (logs)
- Cookie files in `docker/configuration-webserver/site/cookies/`

---

## System-Specific Deployments

For specialized deployment scenarios:

- **CasaOS Legacy** (ZimaBoard): See [`deploy/system-specific/casaos-legacy/`](deploy/system-specific/casaos-legacy/) for older CasaOS versions (0.4.x) that lack Docker Compose import and folder upload features.

## Resources

- **yt-dlp docs**: https://github.com/yt-dlp/yt-dlp
- **gallery-dl docs**: https://github.com/mikf/gallery-dl
- **PyroTGFork docs**: https://telegramplayground.github.io/pyrogram/
- **Telegram Bot API**: https://core.telegram.org/bots/api

---

*Last updated: 2026-03-27*
