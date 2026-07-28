FROM python:3.12-slim

# Install fonts for image generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    fonts-noto \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files
COPY . .

# Use config template if no config.json
RUN if [ ! -f config.json ]; then cp config.template.json config.json; fi

# Run the bot
CMD ["python3", "-u", "bot.py"]
