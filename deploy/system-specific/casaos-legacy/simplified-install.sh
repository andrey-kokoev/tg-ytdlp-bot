#!/usr/bin/env bash
# Simplified Installation Script for CasaOS Legacy
# Run this on the ZimaBoard if you gain SSH access

set -euo pipefail

APP_NAME="tg-ytdlp-bot"
APP_DIR="/DATA/AppData/${APP_NAME}"
REPO_URL="https://github.com/chelaxian/tg-ytdlp-bot.git"

echo "=========================================="
echo "  Installing tg-ytdlp-bot on CasaOS"
echo "=========================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use: sudo bash install.sh)"
   exit 1
fi

# Create directory structure
echo ""
echo "📁 Creating directory structure..."
mkdir -p "${APP_DIR}"/{
    CONFIG,
    TXT,
    docker/configuration-webserver/site/cookies,
    users
}

# Clone repository temporarily to get template files
echo ""
echo "📥 Downloading template files..."
TEMP_DIR=$(mktemp -d)
cd "${TEMP_DIR}"

# Try to download raw files from GitHub (in case git is not available)
curl -fsSL "https://raw.githubusercontent.com/chelaxian/tg-ytdlp-bot/main/CONFIG/_config.py" \
    -o "${APP_DIR}/CONFIG/_config.py" 2>/dev/null || \
    echo "⚠️  Could not download _config.py template"

curl -fsSL "https://raw.githubusercontent.com/chelaxian/tg-ytdlp-bot/main/.env.example" \
    -o "${APP_DIR}/.env" 2>/dev/null || \
    echo "⚠️  Could not download .env template"

curl -fsSL "https://raw.githubusercontent.com/chelaxian/tg-ytdlp-bot/main/docker-compose.yml" \
    -o "${APP_DIR}/docker-compose.yml" 2>/dev/null || \
    echo "⚠️  Could not download docker-compose.yml"

curl -fsSL "https://raw.githubusercontent.com/chelaxian/tg-ytdlp-bot/main/docker-entrypoint.sh" \
    -o "${APP_DIR}/docker-entrypoint.sh" 2>/dev/null || \
    echo "⚠️  Could not download docker-entrypoint.sh"

curl -fsSL "https://raw.githubusercontent.com/chelaxian/tg-ytdlp-bot/main/Dockerfile" \
    -o "${APP_DIR}/Dockerfile" 2>/dev/null || \
    echo "⚠️  Could not download Dockerfile"

curl -fsSL "https://raw.githubusercontent.com/chelaxian/tg-ytdlp-bot/main/requirements.txt" \
    -o "${APP_DIR}/requirements.txt" 2>/dev/null || \
    echo "⚠️  Could not download requirements.txt"

curl -fsSL "https://raw.githubusercontent.com/chelaxian/tg-ytdlp-bot/main/magic.py" \
    -o "${APP_DIR}/magic.py" 2>/dev/null || \
    echo "⚠️  Could not download magic.py"

# Make entrypoint executable
chmod +x "${APP_DIR}/docker-entrypoint.sh" 2>/dev/null || true

# Cleanup
rm -rf "${TEMP_DIR}"

echo ""
echo "✅ Directory structure created at: ${APP_DIR}"
echo ""
echo "📋 Next steps:"
echo "   1. Copy your CONFIG/config.py to: ${APP_DIR}/CONFIG/config.py"
echo "   2. Copy your TXT/cookie.txt to: ${APP_DIR}/TXT/cookie.txt"
echo "   3. Install the app via CasaOS Custom Install"
echo ""
echo "   OR if you have Docker Compose access:"
echo "   cd ${APP_DIR} && docker compose up -d"
echo ""
echo "📁 Directory structure:"
tree "${APP_DIR}" 2>/dev/null || find "${APP_DIR}" -type d | head -20
