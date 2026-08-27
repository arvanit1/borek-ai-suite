FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/apps/services/api:/app/apps/worker

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY apps/services/api ./apps/services/api
COPY apps/worker ./apps/worker
COPY packages/contracts ./packages/contracts

RUN pip install --no-cache-dir .

WORKDIR /app/apps/services/api
CMD ["celery", "-A", "app.worker", "worker", "--loglevel=info"]
