FROM python:3.11-slim

# Install ffmpeg and git for video transcoding and catalog git syncing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV PORT=10000

WORKDIR /app

# Install Python dependencies
COPY tg_bot/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy repository files
COPY . .

EXPOSE 10000

# Run the Telegram bot
CMD ["python", "tg_bot/bot.py"]
