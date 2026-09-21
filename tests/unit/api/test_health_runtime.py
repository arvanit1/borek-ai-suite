"""AT-50/AT-51: runtime mode diagnostics."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.main import create_app
from app.runtime_profile import (
    ProductionFixtureModeError,
    log_runtime_profile,
    runtime_health_payload,
    runtime_warnings,
)


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
    assert body["filing_destination"] in {"fixture", "in_app", "live"}
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


def test_production_fixture_mode_refuses_startup() -> None:
    cfg = Settings(
        _env_file=None,
        RUNTIME_PROFILE="production",
        AI_EXECUTION_MODE="fixture",
        API_DATA_BACKEND="memory",
    )
    with pytest.raises(ProductionFixtureModeError, match="cannot use AI_EXECUTION_MODE=fixture"):
        log_runtime_profile(component="api", current=cfg)


def test_production_live_mode_starts() -> None:
    cfg = Settings(
        _env_file=None,
        RUNTIME_PROFILE="production",
        AI_EXECUTION_MODE="live",
        API_DATA_BACKEND="supabase",
        OPENAI_API_KEY="test-openai-key",
    )
    log_runtime_profile(component="api", current=cfg)


def test_development_fixture_mode_still_starts() -> None:
    cfg = Settings(
        _env_file=None,
        RUNTIME_PROFILE="development",
        AI_EXECUTION_MODE="fixture",
        API_DATA_BACKEND="memory",
    )
    log_runtime_profile(component="api", current=cfg)


def test_runtime_warnings_flag_production_fixture_mode() -> None:
    warnings = runtime_warnings(
        Settings(
            _env_file=None,
            RUNTIME_PROFILE="production",
            AI_EXECUTION_MODE="fixture",
            API_DATA_BACKEND="memory",
        )
    )
    assert any("cannot use AI_EXECUTION_MODE=fixture" in warning for warning in warnings)
