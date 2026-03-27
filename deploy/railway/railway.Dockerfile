# Railway-optimized Dockerfile for tg-ytdlp-bot
# Single-container deployment with all dependencies included

FROM python:3.10-slim

ARG TZ=Europe/Moscow
ENV TZ="$TZ"

# Install all system dependencies (copied from main Dockerfile)
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

# Copy requirements first (for better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire application
COPY . .

# Create necessary directories
RUN mkdir -p CONFIG TXT docker/configuration-webserver/site/cookies users

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Railway uses PORT environment variable (default 5555)
ENV PORT=5555
ENV PYTHONUNBUFFERED=1
ENV COMPOSE_PROJECT_NAME=tg-ytdlp-bot

# Health check for Railway
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose dashboard port
EXPOSE 5555

# Start command
CMD ["bash", "docker-entrypoint.sh"]
