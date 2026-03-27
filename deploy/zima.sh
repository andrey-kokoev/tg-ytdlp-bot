#!/usr/bin/env bash
set -euo pipefail

# ZimaBoard Deployment Script for tg-ytdlp-bot
# Usage: ./zima.sh

# Configuration - EDIT THESE VARIABLES
: "${ZIMA_HOST:=your-zima-ip-or-hostname}"      # e.g., 192.168.1.100 or zima.local
: "${ZIMA_USER:=root}"                           # SSH user (usually root)
: "${REMOTE_DIR:=/root/tg-ytdlp-bot}"            # Remote directory on Zima
: "${LOCAL_DIR:=$(dirname "$(dirname "$(realpath "$0")")")}"  # Auto-detect project root

# SSH Options
SSH_OPTS='-o PreferredAuthentications=password -o PubkeyAuthentication=no'

echo "=========================================="
echo "  Deploying tg-ytdlp-bot to ZimaBoard"
echo "=========================================="
echo "Host:     $ZIMA_HOST"
echo "User:     $ZIMA_USER"
echo "Local:    $LOCAL_DIR"
echo "Remote:   $REMOTE_DIR"
echo "=========================================="

# Validate configuration
if [[ "$ZIMA_HOST" == "your-zima-ip-or-hostname" ]]; then
    echo "❌ ERROR: Please set ZIMA_HOST to your ZimaBoard's IP or hostname"
    echo "   Example: ZIMA_HOST=192.168.1.100 ./zima.sh"
    exit 1
fi

# Sync files to ZimaBoard
echo ""
echo "📤 Syncing files to ZimaBoard..."
rsync -av --delete \
  -e "ssh ${SSH_OPTS}" \
  --filter='P users/**/downloads/**' \
  --filter='P users/**/downloads/' \
  --exclude .git \
  --exclude __pycache__ \
  --exclude .venv \
  --exclude node_modules \
  --exclude bot.log \
  --exclude dump.json \
  --exclude '*.session*' \
  --exclude docker/configuration-webserver/config/caddy \
  --exclude docker/configuration-webserver/data/caddy \
  "$LOCAL_DIR"/ "${ZIMA_USER}@${ZIMA_HOST}:${REMOTE_DIR}/"

# Restart services on ZimaBoard
echo ""
echo "🔄 Restarting services on ZimaBoard..."
ssh -tt ${SSH_OPTS} "${ZIMA_USER}@${ZIMA_HOST}" \
  "cd '${REMOTE_DIR}' && \
   echo 'Pulling latest images...' && \
   docker compose pull && \
   echo 'Building and starting containers...' && \
   docker compose up -d --build && \
   echo '' && \
   echo '✅ Deployment complete!' && \
   echo '' && \
   echo 'Container status:' && \
   docker compose ps && \
   echo '' && \
   echo 'Recent logs:' && \
   docker compose logs --tail=20"

echo ""
echo "✅ Deployment to $ZIMA_HOST complete!"
echo ""
echo "📋 Useful commands:"
echo "   View logs:    ssh $ZIMA_USER@$ZIMA_HOST 'cd $REMOTE_DIR && docker compose logs -f'"
echo "   Stop bot:     ssh $ZIMA_USER@$ZIMA_HOST 'cd $REMOTE_DIR && docker compose down'"
echo "   Restart bot:  ssh $ZIMA_USER@$ZIMA_HOST 'cd $REMOTE_DIR && docker compose restart'"
echo "   Dashboard:    http://$ZIMA_HOST:5555"
