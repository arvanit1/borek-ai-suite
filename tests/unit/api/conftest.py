"""Shared test env for FastAPI unit tests — must run before app imports."""

from __future__ import annotations

import os

import pytest

_TEST_ENV = {
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "OPENAI_API_KEY": "test-openai-key",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "test-supabase-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-supabase-service-role",
    "API_DATA_BACKEND": "memory",
    "AI_EXECUTION_MODE": "fixture",
    "SUPABASE_JWT_SECRET": "test-supabase-jwt-secret-with-32-byte-minimum-length",
    "REDIS_URL": "redis://localhost:6379/0",
    "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/borek",
    "RENDERER_URL": "http://localhost:4000",
    "RENDERER_EXECUTION_MODE": "fixture",
}

for key, value in _TEST_ENV.items():
    os.environ[key] = value

from app.services.data.memory_store import reset_memory_store
from app.services.job_service import reset_job_store


@pytest.fixture(autouse=True)
def _reset_in_memory_backends() -> None:
    reset_memory_store()
    reset_job_store()
