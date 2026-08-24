# AT-9 E2E: LibreOffice + poppler-utils for preview pipeline integration tests.
FROM node:20-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY package.json package-lock.json ./
COPY apps/renderer/package.json apps/renderer/
RUN npm ci

COPY apps/renderer ./apps/renderer
COPY tests/fixtures/renderer/minimal.pptx tests/fixtures/renderer/minimal.pptx
