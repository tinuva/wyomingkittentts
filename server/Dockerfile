# syntax=docker/dockerfile:1

# Lightweight Python base
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System dependencies:
# - espeak-ng: required by phonemizer's EspeakBackend
# - libsndfile1: required by soundfile
# - curl/ca-certificates: for robust HTTPS downloads (Hugging Face, wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    libsndfile1 \
    curl \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first to leverage layer caching
COPY server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy server application
COPY server/app.py /app/app.py

# Expose Wyoming port
EXPOSE 10200

# Server configuration via env (can be overridden at runtime)
ENV HOST=0.0.0.0 \
    PORT=10200 \
    MODEL_ID=KittenML/kitten-tts-nano-0.1 \
    VOICE=expr-voice-5-m \
    SPEED=1.0 \
    SAMPLE_RATE=24000 \
    LOG_LEVEL=INFO

# Optional: create a non-root user (uncomment to enable)
# RUN useradd -m appuser && chown -R appuser:appuser /app
# USER appuser

# Default command runs the Wyoming KittenTTS server
CMD ["python", "/app/app.py"]
