import http from "node:http";

const port = Number(process.env.RENDERER_PORT ?? "4000");

const server = http.createServer((request, response) => {
  if (request.url === "/health") {
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ status: "ok", service: "renderer" }));
    return;
  }

  response.writeHead(404, { "Content-Type": "application/json" });
  response.end(JSON.stringify({ error: { code: "NOT_FOUND", message: "Route not found" } }));
});

server.listen(port, "0.0.0.0", () => {
  console.log(`Renderer service listening on port ${port}`);
});
