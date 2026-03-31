#!/bin/bash
set -e

# Cloudflare Tunnel Setup Script for ytdlp-bot
# Run this on your local machine with Node.js installed

echo "=== Cloudflare Tunnel Setup for ytdlp-bot ==="
echo ""

# Check if wrangler is available
if ! command -v npx &> /dev/null; then
    echo "Error: npx not found. Install Node.js first."
    exit 1
fi

# Check if already logged in
echo "Checking Cloudflare authentication..."
if ! npx wrangler whoami &> /dev/null; then
    echo "Not logged in. Running: npx wrangler login"
    npx wrangler login
fi

TUNNEL_NAME="ytdlp-bot"

echo ""
echo "Creating tunnel: $TUNNEL_NAME"
echo ""

# Create tunnel
TUNNEL_OUTPUT=$(npx wrangler tunnel create "$TUNNEL_NAME" 2>&1)
echo "$TUNNEL_OUTPUT"

# Extract tunnel ID
TUNNEL_ID=$(echo "$TUNNEL_OUTPUT" | grep -oP 'ID:\s*\K[a-f0-9-]+' || true)

if [ -z "$TUNNEL_ID" ]; then
    echo ""
    echo "Tunnel may already exist. Listing tunnels..."
    npx wrangler tunnel list
    echo ""
    echo "Enter tunnel ID from above:"
    read TUNNEL_ID
fi

echo ""
echo "Getting tunnel token..."
TOKEN=$(npx wrangler tunnel token "$TUNNEL_NAME" 2>&1 | grep -v '█' | tr -d '\n' || true)

if [ -z "$TOKEN" ]; then
    echo "Error: Could not get token. Try manually:"
    echo "  npx wrangler tunnel token $TUNNEL_NAME"
    exit 1
fi

echo ""
echo "=== Setup Instructions ==="
echo ""
echo "1. Add this to your .env file:"
echo ""
echo "TUNNEL_TOKEN=$TOKEN"
echo ""
echo "2. In Cloudflare Dashboard (or via API):"
echo "   - Go to Zero Trust → Networks → Tunnels"
echo "   - Click on tunnel: $TUNNEL_NAME"
echo "   - Add Public Hostname:"
echo "     * Subdomain: ytdlp-bot (or your choice)"
echo "     * Domain: yourdomain.com"
echo "     * Path: (leave empty)"
echo "     * Type: HTTP"
echo "     * URL: http://app:5555"
echo ""
echo "3. Start the tunnel:"
echo "   docker compose up -d cloudflared"
echo ""
echo "4. Test:"
echo "   curl https://ytdlp-bot.yourdomain.com/health"
echo ""
echo "Tunnel ID: $TUNNEL_ID"
