"""AT-50/AT-51: runtime mode diagnostics."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.runtime_profile import runtime_health_payload, runtime_warnings


def test_health_runtime_reports_execution_modes() -> None:
    client = TestClient(create_app())
    response = client.get("/health/runtime")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ai_execution_mode"] in {"fixture", "live"}
    assert body["renderer_execution_mode"] in {"fixture", "live"}
    assert body["api_data_backend"] in {"memory", "supabase"}
    assert body["presentation_engine"] in {"internal", "gamma"}
    assert body["gamma_execution_mode"] in {"fixture", "live"}
    assert body["filing_destination"] in {"fixture", "live"}
    assert isinstance(body["warnings"], list)


def test_runtime_warnings_flag_fixture_with_supabase() -> None:
    payload = runtime_health_payload(
        Settings(
            _env_file=None,
            AI_EXECUTION_MODE="fixture",
            RENDERER_EXECUTION_MODE="live",
            API_DATA_BACKEND="supabase",
        )
    )
    assert payload["ai_execution_mode"] == "fixture"
    assert payload["warnings"]


def test_runtime_warnings_flag_live_without_openai_key() -> None:
    warnings = runtime_warnings(
        Settings(
            _env_file=None,
            AI_EXECUTION_MODE="live",
            OPENAI_API_KEY="",
            API_DATA_BACKEND="supabase",
        )
    )
    assert any("OPENAI_API_KEY" in warning for warning in warnings)


def test_runtime_warnings_flag_live_filing_without_repository() -> None:
    warnings = runtime_warnings(
        Settings(
            _env_file=None,
            FILING_DESTINATION="live",
            ENTERPRISE_REPOSITORY_URL="",
            ENTERPRISE_REPOSITORY_TOKEN="",
            API_DATA_BACKEND="memory",
        )
    )
    assert any("ENTERPRISE_REPOSITORY" in warning for warning in warnings)


def test_runtime_warnings_flag_live_gamma_without_key() -> None:
    warnings = runtime_warnings(
        Settings(
            _env_file=None,
            PRESENTATION_ENGINE="gamma",
            GAMMA_EXECUTION_MODE="live",
            GAMMA_API_KEY="",
            API_DATA_BACKEND="memory",
        )
    )
    assert any("GAMMA_API_KEY" in warning for warning in warnings)
