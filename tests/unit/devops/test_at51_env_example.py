"""AT-51: .env.example completeness — every stack env var documented."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = ROOT / ".env.example"

# Canonical variables referenced anywhere in the stack (keep in sync with config + compose + web + scripts).
CANONICAL_ENV_VARS = frozenset(
    {
        # apps/services/api/app/config.py
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_SECRET",
        "SUPABASE_DB_PASSWORD",
        "SUPABASE_DB_POOLER_HOST",
        "DATABASE_URL",
        "REDIS_URL",
        "RENDERER_URL",
        "API_DATA_BACKEND",
        "AI_EXECUTION_MODE",
        "API_HOST",
        "API_PORT",
        # apps/web
        "NEXT_PUBLIC_API_URL",
        "NEXT_PUBLIC_SUPABASE_URL",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        "NEXT_PUBLIC_DEV_ACCESS_TOKEN",
        "NEXT_PUBLIC_WEB_URL",
        "WEB_PORT",
        # apps/renderer
        "RENDERER_PORT",
        "SOFFICE_PATH",
        "LIBREOFFICE_PATH",
        "PDFTOPPM_PATH",
        # docker-compose.yml
        "REDIS_PUBLISH_PORT",
        "API_PUBLISH_PORT",
        "WEB_PUBLISH_PORT",
        "RENDERER_PUBLISH_PORT",
        "PORT",
        # scripts / integration tests
        "RUN_SUPABASE_INTEGRATION",
        "E2E_TEST_EMAIL",
        "E2E_TEST_PASSWORD",
    }
)


def _parse_env_example(path: Path) -> dict[str, str | None]:
    """Return var -> description (from immediately preceding # comment line)."""
    documented: dict[str, str | None] = {}
    pending_description: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            pending_description = line.removeprefix("#").strip()
            continue
        if "=" in line and not line.startswith("#"):
            key = line.split("=", 1)[0].strip()
            documented[key] = pending_description
            pending_description = None

    return documented


def test_at51_env_example_file_exists() -> None:
    assert ENV_EXAMPLE.is_file(), ".env.example must exist at repository root"


def test_at51_env_example_lists_all_canonical_vars() -> None:
    documented = _parse_env_example(ENV_EXAMPLE)
    missing = sorted(CANONICAL_ENV_VARS - set(documented))
    assert not missing, f".env.example missing variables: {missing}"


def test_at51_env_example_each_var_has_one_line_description() -> None:
    documented = _parse_env_example(ENV_EXAMPLE)
    for key in CANONICAL_ENV_VARS:
        description = documented.get(key)
        assert description, f"{key} must have a one-line # description immediately above it in .env.example"
        assert len(description) >= 10, f"{key} description is too short: {description!r}"


def test_at51_env_example_has_no_duplicate_keys() -> None:
    keys: list[str] = []
    for raw_line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.append(line.split("=", 1)[0].strip())
    assert len(keys) == len(set(keys)), "Duplicate keys in .env.example"


def test_at51_env_example_documents_required_supabase_and_llm_keys() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for key in ("SUPABASE_URL", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "REDIS_URL"):
        assert re.search(rf"^{re.escape(key)}=", text, flags=re.MULTILINE)
