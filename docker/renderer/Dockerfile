FROM node:20-bookworm-slim AS deps

WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/renderer/package.json apps/renderer/
RUN npm ci --workspace borek-renderer

FROM node:20-bookworm-slim AS runtime

# AT-9 preview pipeline: LibreOffice (pptx→pdf) + poppler (pdf→png)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libreoffice-writer \
        libreoffice-impress \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/package.json /app/package-lock.json ./
COPY --chown=node:node apps/renderer ./apps/renderer
COPY --chown=node:node packages/contracts ./packages/contracts
COPY --chown=node:node generated/typescript ./generated/typescript

WORKDIR /app/apps/renderer

ENV RENDERER_PORT=4000
ENV SOFFICE_PATH=/usr/bin/soffice
ENV PDFTOPPM_PATH=/usr/bin/pdftoppm
EXPOSE 4000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://127.0.0.1:4000/health || exit 1

USER node
CMD ["npm", "run", "start:server"]
