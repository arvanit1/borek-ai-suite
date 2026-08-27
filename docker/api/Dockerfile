FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/apps/services/api

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY apps/services/api ./apps/services/api
COPY packages/contracts ./packages/contracts

RUN pip install --no-cache-dir .

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

WORKDIR /app/apps/services/api
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
