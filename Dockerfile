# Multi-stage build for smaller image

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (if you need more for torchaudio, add them here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src ./src
COPY configs ./configs
COPY scripts ./scripts

# Optional: copy plugins & UI dashboard
COPY plugins ./plugins
COPY ui ./ui

ENV PYTHONPATH=/app/src

# Default env (overridden by docker-compose or Kubernetes)
ENV AERS_HOST=0.0.0.0 \
    AERS_PORT=8000 \
    AERS_CONFIG_PATH=configs/simple_routing.yaml \
    AERS_PLUGIN_ROOT=plugins

# Expose FastAPI port
EXPOSE 8000

# Start the server using uvicorn
CMD ["uvicorn", "aers.ui.server:app", "--host", "0.0.0.0", "--port", "8000"]

