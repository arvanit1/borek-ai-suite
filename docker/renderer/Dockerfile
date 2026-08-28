FROM node:20-bookworm-slim

# AT-9 preview pipeline: LibreOffice (pptx→pdf) + poppler (pdf→png)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libreoffice-writer \
        libreoffice-impress \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json ./
COPY apps/renderer/package.json apps/renderer/
RUN npm ci --workspace borek-renderer

COPY apps/renderer ./apps/renderer
COPY packages/contracts ./packages/contracts

WORKDIR /app/apps/renderer

ENV RENDERER_PORT=4000
ENV SOFFICE_PATH=/usr/bin/soffice
ENV PDFTOPPM_PATH=/usr/bin/pdftoppm
EXPOSE 4000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://127.0.0.1:4000/health || exit 1

CMD ["npm", "run", "start:server"]
