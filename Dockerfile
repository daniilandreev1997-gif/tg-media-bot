FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg is required by yt-dlp audio post-processing.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/tg-media-bot

COPY tg-media-bot/ /app/tg-media-bot/

RUN pip install --upgrade pip \
    && pip install .

RUN mkdir -p /app/tg-media-bot/data /app/tg-media-bot/data/downloads \
    && chmod -R 777 /app/tg-media-bot/data

CMD ["python", "-m", "app.main"]
