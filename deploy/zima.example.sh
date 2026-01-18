#!/usr/bin/env bash
set -euo pipefail

: "${ZIMA_HOST:?set ZIMA_HOST}"
: "${ZIMA_USER:?set ZIMA_USER}"
: "${REMOTE_DIR:?set REMOTE_DIR}"
: "${LOCAL_DIR:?set LOCAL_DIR}"

SSH_OPTS='-o PreferredAuthentications=password -o PubkeyAuthentication=no'

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

ssh -tt ${SSH_OPTS} "${ZIMA_USER}@${ZIMA_HOST}" \
  "cd '${REMOTE_DIR}' && docker compose up -d --build && docker compose ps"
