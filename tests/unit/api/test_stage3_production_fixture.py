"""Stage 3: production must not silently emit fixture Frameworks."""

from __future__ import annotations

import uuid

import pytest

from app.config import settings
from app.runtime_profile import ProductionFixtureModeError
from app.services.stage_a_orchestration import generate_framework_from_transcripts
from tests.unit.api.test_stage_a_orchestration import OPPORTUNITY_ID, USER_ID, SourceStore, _source


def test_production_refuses_fixture_framework_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", "production")
    monkeypatch.setattr(settings, "AI_EXECUTION_MODE", "fixture")

    with pytest.raises(ProductionFixtureModeError, match="cannot use AI_EXECUTION_MODE=fixture"):
        generate_framework_from_transcripts(
            SourceStore(sources=[_source()]),
            opportunity_id=OPPORTUNITY_ID,
            user_id=USER_ID,
            execution_mode="fixture",
            generate_fn=lambda *_args, **_kwargs: pytest.fail("fixture stub must not run"),
        )


def test_production_live_generate_still_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", "production")
    monkeypatch.setattr(settings, "AI_EXECUTION_MODE", "live")

    result = generate_framework_from_transcripts(
        SourceStore(sources=[_source()]),
        opportunity_id=OPPORTUNITY_ID,
        user_id=USER_ID,
        execution_mode="live",
        extract_fn=lambda *_args, **_kwargs: {"schema_version": "1.0", "conversation_id": "C1", "facts": []},
        generate_fn=lambda *_args, **_kwargs: {
            "schema_version": "1.0",
            "status": "draft",
            "chapters": [],
            "job": str(uuid.uuid4()),
        },
    )
    assert result["status"] == "draft"
