# VØRTΞX System Bot v4 — Koyeb Dockerfile
FROM python:3.12-slim

# Install fonts for Pillow image generation (Arabic + emoji)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    fonts-noto \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY bot.py .
COPY cogs/ cogs/
COPY config.json .
COPY data/ data/

# Set the bot token from environment variable
ENV DISCORD_TOKEN=""

# Run the bot
CMD ["python3", "bot.py"]
