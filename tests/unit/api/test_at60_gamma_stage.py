"""AT-60: feature flag, pipeline stage, observability, and skip path."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.config import settings
from app.schemas.jobs import JOB_PIPELINE_STAGES, JobStage
from app.services.data.memory_store import get_memory_store
from app.services.gamma_stage import (
    gamma_enabled,
    provisional_gamma_slots,
    run_gamma_rendering_stage,
)
from app.services.job_retry import is_transient_failure
from services.gamma.contract import (
    GammaAuthError,
    GammaPayloadError,
    GammaProviderError,
    GammaRateLimitError,
    GammaTemplateError,
    GammaTimeoutError,
)
from services.observability.llm_logger import get_llm_call_logs, reset_llm_call_logs


USER = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def test_gamma_rendering_is_a_pipeline_stage_after_pptx() -> None:
    assert JobStage.GAMMA_RENDERING in JOB_PIPELINE_STAGES
    assert JOB_PIPELINE_STAGES.index(JobStage.PPTX_RENDERING) + 1 == JOB_PIPELINE_STAGES.index(
        JobStage.GAMMA_RENDERING
    )
    assert JOB_PIPELINE_STAGES.index(JobStage.GAMMA_RENDERING) + 1 == JOB_PIPELINE_STAGES.index(
        JobStage.ARTIFACT_FILING
    )
    assert JOB_PIPELINE_STAGES.index(JobStage.ARTIFACT_FILING) + 1 == JOB_PIPELINE_STAGES.index(
        JobStage.PREVIEW_RENDERING
    )


def test_internal_engine_skips_gamma_stage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "internal")
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    store = get_memory_store()
    opportunity = store.create_opportunity(
        user_id=USER,
        client_name="Acme",
        opportunity_name="Automation",
        department="Finance",
        language="en",
        pii_redaction_enabled=True,
        additional_client_information=None,
    )
    result = run_gamma_rendering_stage(
        store,
        job_id=uuid.uuid4(),
        opportunity=opportunity,
        presentation_version_id=uuid.uuid4(),
        user_id=USER,
    )
    assert result == {"skipped": True, "engine": "internal"}
    assert gamma_enabled() is False


def test_gamma_fixture_stage_persists_artifacts_and_observability(
    monkeypatch,
    tmp_path: Path,
) -> None:
    reset_llm_call_logs()
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    monkeypatch.setattr(settings, "GAMMA_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    store = get_memory_store()
    opportunity = store.create_opportunity(
        user_id=USER,
        client_name="Acme",
        opportunity_name="Invoice 3-way Match",
        department="Finance",
        language="en",
        pii_redaction_enabled=True,
        additional_client_information={"notes": "EU hosting required.", "constraints": ["Q4"]},
    )
    job_id = uuid.uuid4()
    version_id = uuid.uuid4()
    result = run_gamma_rendering_stage(
        store,
        job_id=job_id,
        opportunity=opportunity,
        presentation_version_id=version_id,
        user_id=USER,
    )
    assert result["skipped"] is False
    assert result["engine"] == "gamma"
    assert result["branding_locked"] is True
    assert result["template_id"] == "borek-branded-standard"
    assert {item["format"] for item in result["artifacts"]} == {"pptx", "pdf"}
    for artifact in result["artifacts"]:
        path = tmp_path / artifact["storage_key"]
        assert path.is_file()
        assert path.stat().st_size == artifact["byte_size"]
        assert "content" not in artifact
    logs = [row for row in get_llm_call_logs() if row.provider == "gamma"]
    assert len(logs) == 1
    assert logs[0].stage == "gamma_rendering"
    assert logs[0].status == "success"
    durable = store.get_llm_calls_for_job(str(job_id))
    assert durable
    assert durable[0]["provider"] == "gamma"


def test_provisional_slots_are_named_content_only() -> None:
    slots = provisional_gamma_slots(
        opportunity={
            "opportunity_name": "Invoice 3-way Match",
            "client_name": "Acme",
            "department": "Finance",
            "additional_client_information": {"notes": "Berlin delivery"},
        }
    )
    names = [slot.name for slot in slots]
    assert names == [
        "cover.title",
        "cover.client_name",
        "context.summary",
        "scope.in_scope",
        "next_steps.body",
    ]
    assert "brand_color" not in names
    assert all(slot.value.strip() for slot in slots)


def test_gamma_retry_classification_extends_at57() -> None:
    assert is_transient_failure(GammaTimeoutError()) is True
    assert is_transient_failure(GammaRateLimitError()) is True
    assert is_transient_failure(GammaProviderError()) is True
    assert is_transient_failure(GammaAuthError()) is False
    assert is_transient_failure(GammaTemplateError("locked")) is False
    assert is_transient_failure(GammaPayloadError("bad")) is False
