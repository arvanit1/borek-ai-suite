"""AT-50: Docker Compose full-stack wiring."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

REQUIRED_SERVICES = ("redis", "renderer", "api", "worker", "web")
REQUIRED_DOCKERFILES = (
    "docker/api/Dockerfile",
    "docker/worker/Dockerfile",
    "docker/renderer/Dockerfile",
    "docker/web/Dockerfile",
)


def test_at50_compose_declares_required_services() -> None:
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for service in REQUIRED_SERVICES:
        assert f"  {service}:" in compose_text, f"Missing compose service: {service}"


def test_at50_compose_uses_root_env_file() -> None:
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "env_file:" in compose_text
    assert "- .env" in compose_text


def test_at50_compose_wires_internal_dependencies() -> None:
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "REDIS_URL: redis://redis:6379/0" in compose_text
    assert "RENDERER_URL: http://renderer:" in compose_text


def test_at50_dockerfiles_exist() -> None:
    for relative_path in REQUIRED_DOCKERFILES:
        assert (ROOT / relative_path).is_file(), relative_path


def test_at50_renderer_health_server_exists() -> None:
    server_path = ROOT / "apps" / "renderer" / "server.ts"
    text = server_path.read_text(encoding="utf-8")
    assert '"/health"' in text
