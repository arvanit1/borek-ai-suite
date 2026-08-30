"""Shared FastAPI test env for integration tests — must run before app imports."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

_RUN_SUPABASE = os.getenv("RUN_SUPABASE_INTEGRATION") == "1"
_PRESERVE_WHEN_SUPABASE = frozenset(
    {
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_SECRET",
        "SUPABASE_DB_PASSWORD",
        "SUPABASE_DB_POOLER_HOST",
    }
)

_TEST_ENV = {
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "OPENAI_API_KEY": "test-openai-key",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "test-supabase-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-supabase-service-role",
    "API_DATA_BACKEND": "memory",
    "AI_EXECUTION_MODE": "fixture",
    "RENDERER_EXECUTION_MODE": "fixture",
    "SUPABASE_JWT_SECRET": "test-supabase-jwt-secret-with-32-byte-minimum-length",
    "REDIS_URL": "redis://localhost:6379/0",
    "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/borek",
    "RENDERER_URL": "http://localhost:4000",
}

for key, value in _TEST_ENV.items():
    if _RUN_SUPABASE and key in _PRESERVE_WHEN_SUPABASE:
        continue
    os.environ[key] = value

from app.services.data.memory_store import reset_memory_store
from app.services.job_service import reset_job_store
from tests.fixtures.stage_b_test_providers import install_stage_b_test_providers


@pytest.fixture(autouse=True)
def _reset_in_memory_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_memory_store()
    reset_job_store()
    install_stage_b_test_providers(monkeypatch)
