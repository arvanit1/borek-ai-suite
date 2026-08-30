import http from "node:http";

import { RenderServiceError, renderArtifactBundle } from "./render_service.js";

const port = Number(process.env.RENDERER_PORT ?? "4000");
const maxRequestBytes = Number(process.env.RENDERER_MAX_REQUEST_BYTES ?? String(10 * 1024 * 1024));

const server = http.createServer(async (request, response) => {
  if (request.url === "/health") {
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ status: "ok", service: "renderer" }));
    return;
  }

  if (request.method === "POST" && request.url === "/render") {
    try {
      const body = await readJsonBody(request);
      const bundle = await renderArtifactBundle(body);
      response.writeHead(200, {
        "Content-Type": "application/zip",
        "Content-Length": String(bundle.length),
        "Cache-Control": "no-store",
      });
      response.end(bundle);
    } catch (error) {
      const statusCode = error instanceof RenderServiceError ? error.statusCode : 500;
      const code = error instanceof RenderServiceError ? error.code : "RENDER_FAILED";
      const message = error instanceof Error ? error.message : String(error);
      const details = error instanceof RenderServiceError ? error.details : undefined;
      response.writeHead(statusCode, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ error: { code, message, details } }));
    }
    return;
  }

  response.writeHead(404, { "Content-Type": "application/json" });
  response.end(JSON.stringify({ error: { code: "NOT_FOUND", message: "Route not found" } }));
});

async function readJsonBody(request: http.IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  let received = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    received += buffer.length;
    if (received > maxRequestBytes) {
      throw new RenderServiceError("REQUEST_TOO_LARGE", "Render request is too large", 413);
    }
    chunks.push(buffer);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new RenderServiceError("INVALID_JSON", "Request body must be valid JSON", 400);
  }
}

server.listen(port, "0.0.0.0", () => {
  console.log(`Renderer service listening on port ${port}`);
});
