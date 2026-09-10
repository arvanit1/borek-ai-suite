"""BT-30: new-direction end-to-end acceptance gate.

Extends the BT-27 full-pipeline harness. Automated tests use the Gamma
fixture provider; live Gamma evidence is the already-completed AT-60B run.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.schemas.jobs import JobStage
from app.services import job_service
from app.services.data.memory_store import get_memory_store
from services.gamma.contract import GammaTimeoutError
from services.gamma.fixture_client import FixtureGammaClient
from services.gamma.payload import build_gamma_content_payload
from tests.integration.full_pipeline.harness import (
    _find_backend_generation_job,
    _wait_for_job,
    create_opportunity_with_transcript,
    generate_and_confirm_framework,
    get_active_job,
    record_job_stages,
    run_automated_pipeline,
    stages_for_job,
)
from tests.integration.full_pipeline.test_bt27_e2e_gate import (
    EXPECTED_FRAMEWORK_STAGES,
    frontend_stage_labels,
    jobs_for,
)

USER_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
TEST_JWT_SECRET = "test-supabase-jwt-secret-with-32-byte-minimum-length"
ROOT = Path(__file__).resolve().parents[3]
JOB_PROGRESS_TS = ROOT / "apps" / "web" / "src" / "lib" / "jobProgress.ts"
JOB_ERRORS_TS = ROOT / "apps" / "web" / "src" / "lib" / "jobErrors.ts"
RECOVERY_TS = ROOT / "apps" / "web" / "src" / "lib" / "recoveryUx.ts"

EXPECTED_GAMMA_GENERATION_STAGES = (
    JobStage.SLIDE_GENERATING.value,
    JobStage.SLIDE_VALIDATING.value,
    JobStage.GAMMA_RENDERING.value,
    JobStage.ARTIFACT_FILING.value,
    JobStage.PREVIEW_RENDERING.value,
)


@pytest.fixture
def headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=USER_ID,
        email="bt30@example.com",
        secret=TEST_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "API_DATA_BACKEND", "memory")
    monkeypatch.setattr(settings, "AI_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "RENDERER_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    monkeypatch.setattr(settings, "GAMMA_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    return TestClient(create_app())


def _eligibility(
    client: TestClient,
    headers: dict[str, str],
    opportunity_id: str,
    journey_stage: str | None = None,
) -> dict:
    params = {"journey_stage": journey_stage} if journey_stage else None
    response = client.get(
        f"/opportunities/{opportunity_id}/journey-stage-eligibility",
        headers=headers,
        params=params,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _latest_version(presentation_id: str) -> dict:
    return get_memory_store().get_latest_presentation_version(
        presentation_id=uuid.UUID(presentation_id),
        user_id=USER_ID,
    )


def _newest_generation_job(opportunity_id: str, *, exclude: set[str] | None = None) -> str:
    rows = jobs_for(opportunity_id, "presentation_generation")
    if exclude:
        rows = [row for row in rows if str(row["id"]) not in exclude]
    assert rows, f"no generation jobs for {opportunity_id}"
    latest = max(rows, key=lambda row: str(row.get("created_at") or row["id"]))
    return str(latest["id"])


def _continue_automated_build(
    client: TestClient,
    *,
    headers: dict[str, str],
    opportunity_id: str,
    framework_version_id: str,
    journey_stage: str,
    exclude_generation_ids: set[str] | None = None,
) -> tuple[str, str, tuple[str, ...]]:
    existing = {str(row["id"]) for row in jobs_for(opportunity_id, "presentation_generation")}
    if exclude_generation_ids:
        existing.update(exclude_generation_ids)
    with record_job_stages() as recorded:
        plan = client.post(
            f"/opportunities/{opportunity_id}/presentation-plan/generate",
            headers=headers,
            json={
                "framework_version_id": framework_version_id,
                "auto_continue": True,
                "journey_stage": journey_stage,
            },
        )
        assert plan.status_code == 202, plan.text
        _wait_for_job(client, headers=headers, job_id=str(plan.json()["job_id"]))
        generation_job_id = _newest_generation_job(opportunity_id, exclude=existing)
        job = _wait_for_job(client, headers=headers, job_id=generation_job_id)
    presentation_id = str((job.get("result") or {}).get("presentation_id") or "")
    assert presentation_id
    return generation_job_id, presentation_id, stages_for_job(recorded, generation_job_id)


def test_bt30_english_first_contact_gamma_happy_path(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    opportunity_id, _ = create_opportunity_with_transcript(
        client,
        headers=headers,
        opportunity_name="BT-30 English Happy Path",
        additional_client_information={"notes": "Optional intake must not block."},
    )
    before = _eligibility(client, headers, opportunity_id)
    stages = {row["journey_stage"]: row for row in before["stages"]}
    assert stages["first_contact"]["startable"] is True
    assert stages["deepening"]["startable"] is False
    assert stages["concretisation"]["startable"] is False
    assert before["startable"] is True

    deepening_locked = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=headers,
        json={"journey_stage": "deepening", "auto_continue": True},
    )
    assert deepening_locked.status_code == 400
    assert deepening_locked.json()["error"]["code"] == "INPUT_REQUIRED"

    framework_version_id, _, framework_stages = generate_and_confirm_framework(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
    )
    generation_job_id, presentation_id, generation_stages = _continue_automated_build(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
        framework_version_id=framework_version_id,
        journey_stage="first_contact",
    )
    generation_job = client.get(f"/jobs/{generation_job_id}", headers=headers)
    presentation_version_id = str(generation_job.json()["result"]["presentation_version_id"])

    assert framework_stages == EXPECTED_FRAMEWORK_STAGES
    assert generation_stages == EXPECTED_GAMMA_GENERATION_STAGES
    assert JobStage.PPTX_RENDERING.value not in generation_stages
    assert len(jobs_for(opportunity_id, "presentation_planning")) == 1
    assert len(jobs_for(opportunity_id, "presentation_generation")) == 1

    version = _latest_version(presentation_id)
    assert version["journey_stage"] == "first_contact"
    assert version["prior_stage_presentation_version_id"] is None
    assert version["status"] == "ready"

    framework = client.get(f"/opportunities/{opportunity_id}/framework", headers=headers)
    assert framework.status_code == 200
    assert framework.json()["status"] == "confirmed"
    store = get_memory_store()
    opportunity = store.get_opportunity(
        opportunity_id=uuid.UUID(opportunity_id),
        user_id=USER_ID,
    )
    payload = build_gamma_content_payload(
        opportunity=opportunity,
        framework=framework.json().get("framework_json") or framework.json(),
        stage="first_contact",
    )
    slot_names = {slot["name"] for slot in payload["slots"]}
    assert "pricing.body" not in slot_names
    assert payload["template_id"]
    assert all("price" not in name for name in slot_names)

    after = _eligibility(client, headers, opportunity_id, "deepening")
    assert after["startable"] is True
    assert after["prior_stage_presentation_version_id"] == presentation_version_id
    concretisation = _eligibility(client, headers, opportunity_id, "concretisation")
    assert concretisation["startable"] is False
    assert concretisation["next_action"] == "complete_deepening"

    filed = client.get(f"/opportunities/{opportunity_id}/filed-artifacts", headers=headers)
    assert filed.status_code == 200, filed.text
    kinds = {row["artifact_kind"] for row in filed.json()}
    assert {"pptx", "pdf"} <= kinds
    for row in filed.json():
        assert str(row["presentation_version_id"]) == presentation_version_id
        assert row.get("destination_path")
        assert row.get("provider")

    pptx = client.get(f"/presentations/{presentation_id}/download/pptx", headers=headers)
    pdf = client.get(f"/presentations/{presentation_id}/download/pdf", headers=headers)
    assert pptx.status_code == 200 and len(pptx.content) > 0
    assert pdf.status_code == 200 and len(pdf.content) > 0

    deck = client.get(f"/presentations/{presentation_id}/deck", headers=headers)
    assert deck.status_code == 200, deck.text
    assert "engine" not in deck.json()
    assert "gamma" not in deck.text.lower()
    preview = client.get(deck.json()["slides"][0]["preview_url"], headers=headers)
    assert preview.status_code == 200
    assert preview.content.startswith(b"\x89PNG")

    labels = frontend_stage_labels()
    for stage in EXPECTED_GAMMA_GENERATION_STAGES:
        assert labels[stage] != stage
        assert "gamma" not in labels[stage].lower()
        assert "%" not in labels[stage]
    assert labels["GAMMA_RENDERING"] == "Building your presentation"
    assert labels["ARTIFACT_FILING"] == "Archiving generated files"
    progress_source = JOB_PROGRESS_TS.read_text(encoding="utf-8")
    assert 'BOREK_RETRIEVAL_STAGE]: "Retrieving Borek information"' in progress_source
    assert not re.search(r"\bGamma\b", " ".join(labels.values()))

    planning_before = len(jobs_for(opportunity_id, "presentation_planning"))
    generation_before = len(jobs_for(opportunity_id, "presentation_generation"))
    for stage_group in ("framework", "presentation"):
        active = get_active_job(
            client,
            headers=headers,
            opportunity_id=opportunity_id,
            stage_group=stage_group,
        )
        assert active is not None
        assert active["status"] in {"COMPLETED", "RUNNING", "QUEUED"}
    assert len(jobs_for(opportunity_id, "presentation_planning")) == planning_before
    assert len(jobs_for(opportunity_id, "presentation_generation")) == generation_before


def test_bt30_in_flight_approve_reuses_generation_job(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    opportunity_id, _ = create_opportunity_with_transcript(
        client,
        headers=headers,
        opportunity_name="BT-30 Reconnect",
    )
    framework_version_id, _, _ = generate_and_confirm_framework(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
    )
    inflight = job_service.create_job(
        uuid.UUID(opportunity_id),
        "presentation_generation",
        enqueue={
            "user_id": str(USER_ID),
            "presentation_id": str(uuid.uuid4()),
            "journey_stage": "first_contact",
        },
        repository=get_memory_store(),
    )
    reused = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=headers,
        json={
            "framework_version_id": framework_version_id,
            "journey_stage": "first_contact",
        },
    )
    assert reused.status_code == 202, reused.text
    assert reused.json()["is_existing_job"] is True
    assert reused.json()["job_id"] == str(inflight.id)
    assert jobs_for(opportunity_id, "presentation_planning") == []
    assert len(jobs_for(opportunity_id, "presentation_generation")) == 1


def test_bt30_deepening_unlocks_after_completed_first_contact(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    first = run_automated_pipeline(
        client,
        headers=headers,
        opportunity_name="BT-30 Deepening Unlock",
        journey_stage="first_contact",
    )
    deepening_job_id, deepening_presentation_id, deepening_stages = _continue_automated_build(
        client,
        headers=headers,
        opportunity_id=first.opportunity_id,
        framework_version_id=first.framework_version_id,
        journey_stage="deepening",
    )
    assert JobStage.GAMMA_RENDERING.value in deepening_stages
    deepening = _latest_version(deepening_presentation_id)
    assert deepening["journey_stage"] == "deepening"
    assert str(deepening["prior_stage_presentation_version_id"]) == first.presentation_version_id
    assert deepening_job_id

    unlocked = _eligibility(client, headers, first.opportunity_id, "concretisation")
    assert unlocked["startable"] is True
    assert unlocked["prior_stage_presentation_version_id"] == str(deepening["id"])


def test_bt30_classified_gamma_failure_recovers_without_dead_end(
    client: TestClient,
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"count": 0}
    original = FixtureGammaClient.generate

    def _flaky(self, request):
        attempts["count"] += 1
        if attempts["count"] <= 2:
            raise GammaTimeoutError()
        return original(self, request)

    monkeypatch.setattr(FixtureGammaClient, "generate", _flaky)

    opportunity_id, _ = create_opportunity_with_transcript(
        client,
        headers=headers,
        opportunity_name="BT-30 Gamma Recovery",
    )
    framework_version_id, _, _ = generate_and_confirm_framework(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
    )
    plan = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=headers,
        json={
            "framework_version_id": framework_version_id,
            "auto_continue": True,
            "journey_stage": "first_contact",
        },
    )
    assert plan.status_code == 202, plan.text
    _wait_for_job(client, headers=headers, job_id=str(plan.json()["job_id"]))
    generation_job_id, _ = _find_backend_generation_job(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
    )
    failed = _wait_for_job(
        client,
        headers=headers,
        job_id=generation_job_id,
        allow_failed=True,
    )
    assert failed["status"] == "FAILED"
    assert failed["error"]["code"] == "GAMMA_TIMEOUT"
    assert failed["error"]["stage"] == JobStage.GAMMA_RENDERING.value
    assert failed["error"]["retryable"] is True

    framework = client.get(f"/opportunities/{opportunity_id}/framework", headers=headers)
    assert framework.json()["status"] == "confirmed"
    persisted_plan = client.get(
        f"/opportunities/{opportunity_id}/presentation-plan",
        headers=headers,
    )
    assert persisted_plan.status_code == 200
    assert persisted_plan.json()["id"] == plan.json()["presentation_plan_id"]
    assert jobs_for(opportunity_id, "presentation_generation") == [
        job for job in jobs_for(opportunity_id, "presentation_generation")
    ]
    assert len(jobs_for(opportunity_id, "presentation_generation")) == 1

    errors_source = JOB_ERRORS_TS.read_text(encoding="utf-8")
    assert "GAMMA_TIMEOUT" in errors_source
    recovery_source = RECOVERY_TS.read_text(encoding="utf-8")
    assert "RETRY" in recovery_source

    retry = client.post(f"/jobs/{generation_job_id}/retry", headers=headers)
    assert retry.status_code == 202, retry.text
    recovered = _wait_for_job(client, headers=headers, job_id=generation_job_id)
    assert recovered["status"] == "COMPLETED"
    presentation_id = recovered["result"]["presentation_id"]
    version = _latest_version(presentation_id)
    assert version["status"] == "ready"
    assert version["journey_stage"] == "first_contact"
    pptx = client.get(f"/presentations/{presentation_id}/download/pptx", headers=headers)
    assert pptx.status_code == 200 and len(pptx.content) > 0
    assert len(jobs_for(opportunity_id, "presentation_planning")) == 1
    assert len(jobs_for(opportunity_id, "presentation_generation")) == 1
    assert attempts["count"] >= 3


def test_bt30_german_smoke_reaches_ready(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    result = run_automated_pipeline(
        client,
        headers=headers,
        language="de",
        journey_stage="first_contact",
        opportunity_name="BT-30 German Smoke",
        client_name="Musterkunde GmbH",
    )
    opportunity = client.get(f"/opportunities/{result.opportunity_id}", headers=headers)
    assert opportunity.status_code == 200
    assert opportunity.json()["language"] == "de"
    framework = client.get(
        f"/opportunities/{result.opportunity_id}/framework",
        headers=headers,
    )
    assert framework.json()["status"] == "confirmed"
    rendered = client.get(
        f"/frameworks/{result.framework_version_id}/render",
        headers=headers,
        params={"format": "docx", "lang": "de"},
    )
    assert rendered.status_code == 200, rendered.text
    assert result.generation_stages == EXPECTED_GAMMA_GENERATION_STAGES
    version = _latest_version(result.presentation_id)
    assert version["status"] == "ready"
    pptx = client.get(f"/presentations/{result.presentation_id}/download/pptx", headers=headers)
    pdf = client.get(f"/presentations/{result.presentation_id}/download/pdf", headers=headers)
    assert pptx.status_code == 200 and len(pptx.content) > 0
    assert pdf.status_code == 200 and len(pdf.content) > 0


def test_bt30_flag_off_keeps_internal_renderer(
    monkeypatch: pytest.MonkeyPatch,
    headers: dict[str, str],
) -> None:
    monkeypatch.setattr(settings, "API_DATA_BACKEND", "memory")
    monkeypatch.setattr(settings, "AI_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "RENDERER_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "internal")
    monkeypatch.setattr(settings, "GAMMA_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    client = TestClient(create_app())
    result = run_automated_pipeline(
        client,
        headers=headers,
        opportunity_name="BT-30 Internal Flag Off",
    )
    assert JobStage.PPTX_RENDERING.value in result.generation_stages
    assert JobStage.GAMMA_RENDERING.value not in result.generation_stages
