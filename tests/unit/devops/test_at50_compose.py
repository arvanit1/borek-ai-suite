"""AT-50: Docker Compose full-stack wiring."""

from __future__ import annotations

import re
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


def test_at50_compose_declares_worker_healthcheck() -> None:
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    worker_block = compose_text.split("  worker:")[1].split("\n  web:")[0]
    assert "healthcheck:" in worker_block
    assert "celery -A app.worker inspect ping" in worker_block


def test_at50_dockerfiles_exist() -> None:
    for relative_path in REQUIRED_DOCKERFILES:
        assert (ROOT / relative_path).is_file(), relative_path


def test_at50_api_dockerfile_includes_deck_fixture() -> None:
    dockerfile = (ROOT / "docker/api/Dockerfile").read_text(encoding="utf-8")
    assert "tests/fixtures/renderer" in dockerfile


def test_at50_contracts_ship_confirmed_group_frameworks() -> None:
    """Fixture-mode API/worker images copy packages/; those fixtures must be there."""
    fixtures = ROOT / "packages" / "contracts" / "fixtures"
    for group in ("a", "b", "c"):
        path = fixtures / f"framework_object.confirmed.group_{group}.json"
        assert path.is_file(), path
    dockerfile = (ROOT / "docker/api/Dockerfile").read_text(encoding="utf-8")
    worker = (ROOT / "docker/worker/Dockerfile").read_text(encoding="utf-8")
    assert "COPY packages" in dockerfile
    assert "COPY packages" in worker


def test_at50_renderer_dockerfile_includes_preview_tooling() -> None:
    dockerfile = (ROOT / "docker/renderer/Dockerfile").read_text(encoding="utf-8")
    assert "libreoffice" in dockerfile.lower()
    assert "poppler-utils" in dockerfile


def test_at50_web_dockerfile_copies_public_assets() -> None:
    dockerfile = (ROOT / "docker/web/Dockerfile").read_text(encoding="utf-8")
    assert "apps/web/public" in dockerfile


def test_at50_pyproject_includes_redis_for_celery_worker() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'"redis>=', pyproject)


def test_at50_renderer_health_server_exists() -> None:
    server_path = ROOT / "apps" / "renderer" / "server.ts"
    text = server_path.read_text(encoding="utf-8")
    assert '"/health"' in text
