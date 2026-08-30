FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps/services/api ./apps/services/api
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/apps/services/api:/app/apps/api

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /artifacts \
    && chown appuser:appuser /artifacts

COPY --from=builder /install /usr/local
COPY apps/services/api ./apps/services/api
COPY apps/api ./apps/api
COPY generated/python ./generated/python
COPY config ./config
COPY packages ./packages
COPY tests/fixtures/renderer ./tests/fixtures/renderer

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

WORKDIR /app/apps/services/api
USER appuser
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
