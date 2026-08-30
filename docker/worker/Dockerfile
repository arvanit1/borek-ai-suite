FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps/services/api ./apps/services/api
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/apps/services/api:/app/apps/api:/app/apps/worker

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /artifacts \
    && chown appuser:appuser /artifacts

COPY --from=builder /install /usr/local
COPY apps/services/api ./apps/services/api
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY generated/python ./generated/python
COPY config ./config
COPY packages ./packages

WORKDIR /app/apps/services/api

HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=40s \
  CMD celery -A app.worker inspect ping --timeout 5 2>&1 | grep -q pong || exit 1

USER appuser
CMD ["celery", "-A", "app.worker", "worker", "--loglevel=info"]
