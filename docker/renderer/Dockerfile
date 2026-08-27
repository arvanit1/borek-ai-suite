FROM node:20-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json ./
COPY apps/renderer/package.json apps/renderer/
RUN npm ci --workspace borek-renderer

COPY apps/renderer ./apps/renderer
COPY packages/contracts ./packages/contracts

WORKDIR /app/apps/renderer

ENV RENDERER_PORT=4000
EXPOSE 4000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://127.0.0.1:4000/health || exit 1

CMD ["npm", "run", "start:server"]
