FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/apps/services/api:/app/apps/api:/app/apps/worker

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY apps/services/api ./apps/services/api
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY config ./config
COPY packages ./packages

RUN pip install --no-cache-dir .

WORKDIR /app/apps/services/api

HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=40s \
  CMD celery -A app.worker inspect ping --timeout 5 2>&1 | grep -q pong || exit 1

CMD ["celery", "-A", "app.worker", "worker", "--loglevel=info"]
