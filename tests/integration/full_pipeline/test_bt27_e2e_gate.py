"""BT-27: final automated end-to-end integration gate.

Proves the merged Pitch Factory workflow: transcript → Framework → human
approval → automated planning → backend-owned continuation → slide generation →
validation → rendering → preview → retrievable presentation.

Boundaries exercised here (honest, not a live Docker E2E):

  real      FastAPI app, routers, services, job state machine, worker task
            bodies via in-process ``task.run()`` (memory backend), plan/slide/
            version persistence, artifact files
  fixture   LLM calls (AI_EXECUTION_MODE=fixture, deterministic Stage B
            providers), renderer (RENDERER_EXECUTION_MODE=fixture)
  in-memory data store (API_DATA_BACKEND=memory) instead of Supabase
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
from app.services import job_service, presentation_generation
from app.services.data.memory_store import get_memory_store
from tests.integration.full_pipeline.harness import (
    create_opportunity_with_transcript,
    generate_and_confirm_framework,
    get_active_job,
    run_automated_pipeline,
)

USER_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
ROOT = Path(__file__).resolve().parents[3]
JOB_PROGRESS_TS = ROOT / "apps" / "web" / "src" / "lib" / "jobProgress.ts"

# The stages the production workers emit for the automated build (v2 §24).
EXPECTED_FRAMEWORK_STAGES = (
    JobStage.TRANSCRIPT_PROCESSING.value,
    JobStage.KNOWLEDGE_EXTRACTING.value,
    JobStage.FRAMEWORK_SYNTHESIZING.value,
    JobStage.FRAMEWORK_VALIDATING.value,
)
EXPECTED_GENERATION_STAGES = (
    JobStage.SLIDE_GENERATING.value,
    JobStage.SLIDE_VALIDATING.value,
    JobStage.PPTX_RENDERING.value,
    JobStage.PREVIEW_RENDERING.value,
)


@pytest.fixture
def headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=USER_ID,
        email="bt27@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "API_DATA_BACKEND", "memory")
    monkeypatch.setattr(settings, "AI_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "RENDERER_EXECUTION_MODE", "fixture")
    return TestClient(create_app())


def jobs_for(opportunity_id: str, job_type: str) -> list[dict]:
    target = uuid.UUID(opportunity_id)
    return [
        row
        for row in get_memory_store().generation_jobs.values()
        if row.get("opportunity_id") == target and row.get("job_type") == job_type
    ]


def frontend_stage_labels() -> dict[str, str]:
    """Customer-facing labels BT-26 ships, read from the frontend source."""
    source = JOB_PROGRESS_TS.read_text(encoding="utf-8")
    block = re.search(r"JOB_STAGE_LABELS: Record<string, string> = \{(.*?)\n\};", source, re.S)
    assert block, "could not locate JOB_STAGE_LABELS in jobProgress.ts"
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"^\s*([A-Z0-9_]+):\s*\"([^\"]+)\"", block.group(1), re.M)
    }


def test_bt27_automated_build_reaches_a_retrievable_presentation(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    result = run_automated_pipeline(client, headers=headers)

    # A. Framework: real stages ran and the version persisted.
    assert result.framework_stages == EXPECTED_FRAMEWORK_STAGES, result.framework_stages
    framework = client.get(
        f"/opportunities/{result.opportunity_id}/framework",
        headers=headers,
    )
    assert framework.status_code == 200, framework.text
    assert framework.json()["id"] == result.framework_version_id
    assert framework.json()["status"] == "confirmed"

    # B. Planning: exactly one planning job, carrying the automated intent.
    planning_jobs = jobs_for(result.opportunity_id, "presentation_planning")
    assert len(planning_jobs) == 1, planning_jobs
    assert not result.planning_reused
    planning_job = client.get(f"/jobs/{result.planning_job_id}", headers=headers)
    assert planning_job.status_code == 200, planning_job.text
    assert planning_job.json()["status"] == "COMPLETED"
    assert planning_job.json()["job_type"] == "presentation_planning"
    assert planning_job.json()["result"]["_enqueue"]["auto_continue"] is True
    assert planning_job.json()["result"]["presentation_plan_id"] == result.presentation_plan_id

    # C. Automatic handoff: the backend started generation, exactly once, with
    # no presentation-generation request from this client.
    generation_jobs = jobs_for(result.opportunity_id, "presentation_generation")
    assert len(generation_jobs) == 1, generation_jobs
    assert str(generation_jobs[0]["id"]) == result.generation_job_id

    # D. Generation: the real stage sequence, in order.
    assert result.generation_stages == EXPECTED_GENERATION_STAGES, result.generation_stages

    # E. Persistence and identifiers all point at one another.
    plan = client.get(
        f"/opportunities/{result.opportunity_id}/presentation-plan",
        headers=headers,
    )
    assert plan.status_code == 200, plan.text
    assert plan.json()["id"] == result.presentation_plan_id
    assert plan.json()["framework_version_id"] == result.framework_version_id
    assert len(plan.json()["plan_json"]["slides"]) == len(result.slide_ids)

    presentation = client.get(f"/presentations/{result.presentation_id}", headers=headers)
    assert presentation.status_code == 200, presentation.text
    assert presentation.json()["presentation_plan_id"] == result.presentation_plan_id

    latest = client.get(
        f"/opportunities/{result.opportunity_id}/presentation",
        headers=headers,
    )
    assert latest.status_code == 200, latest.text
    assert latest.json()["id"] == result.presentation_id

    # F. Artifacts belong to the generated version and are non-empty.
    assert result.pptx_bytes.startswith(b"PK"), "PPTX must be a ZIP container"
    assert len(result.pptx_bytes) > 1000, f"PPTX looks like a stub ({len(result.pptx_bytes)} bytes)"
    pdf = client.get(f"/presentations/{result.presentation_id}/download/pdf", headers=headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")

    # G. Frontend contract: Deck Center resolves this exact presentation, and
    # every stage the run really emitted has a BT-26 customer-facing label.
    deck = client.get(f"/presentations/{result.presentation_id}/deck", headers=headers)
    assert deck.status_code == 200, deck.text
    deck_payload = deck.json()
    assert deck_payload["presentation_id"] == result.presentation_id
    assert len(deck_payload["slides"]) == len(result.slide_ids)
    assert deck_payload["pptx_download_url"].endswith("/download/pptx")
    preview = client.get(deck_payload["slides"][0]["preview_url"], headers=headers)
    assert preview.status_code == 200, preview.text
    assert preview.content.startswith(b"\x89PNG")
    labels = frontend_stage_labels()
    for stage in result.framework_stages + result.generation_stages:
        assert stage in labels, f"stage {stage} has no BT-26 label"
        assert labels[stage] != stage

    # H. Reconnect: AT-56 answers for this opportunity and creates nothing.
    for stage_group in ("framework", "presentation"):
        active = get_active_job(
            client,
            headers=headers,
            opportunity_id=result.opportunity_id,
            stage_group=stage_group,
        )
        assert active is not None, f"no reconnectable {stage_group} job"
        assert active["status"] in {"COMPLETED", "RUNNING", "QUEUED"}
    assert len(jobs_for(result.opportunity_id, "presentation_planning")) == 1
    assert len(jobs_for(result.opportunity_id, "presentation_generation")) == 1

    # Every slide carries a validated SlideSpec and a real layout.
    slides = client.get(f"/presentations/{result.presentation_id}/slides", headers=headers)
    assert slides.status_code == 200, slides.text
    for slide in slides.json():
        assert slide["layout_id"]
        assert slide["slide_spec"]


def test_bt27_planning_requires_human_framework_confirmation(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    opportunity_id, _ = create_opportunity_with_transcript(
        client,
        headers=headers,
        opportunity_name="BT-27 Confirmation Gate",
    )
    generate = client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=headers)
    assert generate.status_code == 202, generate.text
    framework_version_id = generate.json()["framework_version_id"]

    premature = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=headers,
        json={"framework_version_id": framework_version_id, "auto_continue": True},
    )
    assert premature.status_code == 400, premature.text
    assert premature.json()["error"]["code"] == "FRAMEWORK_NOT_CONFIRMED"
    assert jobs_for(opportunity_id, "presentation_planning") == []
    assert jobs_for(opportunity_id, "presentation_generation") == []


def test_bt27_manual_plan_flow_stays_manual(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    """Plan Preview remains optional: without auto_continue nothing continues."""
    opportunity_id, _ = create_opportunity_with_transcript(
        client,
        headers=headers,
        opportunity_name="BT-27 Manual Plan",
    )
    framework_version_id, _, _ = generate_and_confirm_framework(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
    )

    plan = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=headers,
        json={"framework_version_id": framework_version_id},
    )
    assert plan.status_code == 202, plan.text
    job = client.get(f"/jobs/{plan.json()['job_id']}", headers=headers)
    assert job.status_code == 200, job.text
    assert job.json()["status"] == "COMPLETED"
    assert job.json()["result"]["_enqueue"]["auto_continue"] is False
    assert jobs_for(opportunity_id, "presentation_generation") == []

    # The persisted plan is still readable for Plan Preview.
    persisted = client.get(
        f"/opportunities/{opportunity_id}/presentation-plan",
        headers=headers,
    )
    assert persisted.status_code == 200, persisted.text
    assert persisted.json()["plan_json"]["slides"]


def test_bt27_active_planning_is_reused_not_duplicated(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    """AT-56 reuse: reconnecting to in-flight planning posts no second job."""
    opportunity_id, _ = create_opportunity_with_transcript(
        client,
        headers=headers,
        opportunity_name="BT-27 Planning Reuse",
    )
    framework_version_id, _, _ = generate_and_confirm_framework(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
    )
    store = get_memory_store()
    inflight = job_service.create_job(
        uuid.UUID(opportunity_id),
        "presentation_planning",
        enqueue={
            "framework_version_id": framework_version_id,
            "user_id": str(USER_ID),
            "presentation_plan_id": str(uuid.uuid4()),
        },
        repository=store,
    )

    active = get_active_job(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
        stage_group="presentation",
    )
    assert active is not None
    assert active["job_id"] == str(inflight.id)
    assert active["job_type"] == "presentation_planning"

    upgraded = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=headers,
        json={"framework_version_id": framework_version_id, "auto_continue": True},
    )
    assert upgraded.status_code == 202, upgraded.text
    assert upgraded.json()["is_existing_job"] is True
    assert upgraded.json()["job_id"] == str(inflight.id)
    assert len(jobs_for(opportunity_id, "presentation_planning")) == 1
    assert jobs_for(opportunity_id, "presentation_generation") == []

    # The automated intent is now durable on the reused job.
    reused = client.get(f"/jobs/{inflight.id}", headers=headers)
    assert reused.status_code == 200, reused.text
    assert reused.json()["result"]["_enqueue"]["auto_continue"] is True


def test_bt27_active_generation_is_recovered_without_new_planning(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    """AT-56 reconnect: an in-flight generation job is recovered, not re-planned."""
    opportunity_id, _ = create_opportunity_with_transcript(
        client,
        headers=headers,
        opportunity_name="BT-27 Generation Reuse",
    )
    framework_version_id, _, _ = generate_and_confirm_framework(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
    )
    inflight = job_service.create_job(
        uuid.UUID(opportunity_id),
        "presentation_generation",
        enqueue={"user_id": str(USER_ID), "presentation_id": str(uuid.uuid4())},
        repository=get_memory_store(),
    )

    active = get_active_job(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
        stage_group="presentation",
    )
    assert active is not None
    assert active["job_id"] == str(inflight.id)
    assert active["job_type"] == "presentation_generation"

    reused = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=headers,
        json={"framework_version_id": framework_version_id},
    )
    assert reused.status_code == 202, reused.text
    assert reused.json()["is_existing_job"] is True
    assert reused.json()["job_id"] == str(inflight.id)
    assert jobs_for(opportunity_id, "presentation_planning") == []
    assert len(jobs_for(opportunity_id, "presentation_generation")) == 1


def test_bt27_planning_failure_does_not_start_generation(
    client: TestClient,
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opportunity_id, _ = create_opportunity_with_transcript(
        client,
        headers=headers,
        opportunity_name="BT-27 Planning Failure",
    )
    framework_version_id, _, _ = generate_and_confirm_framework(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
    )

    def _fail(*_args, **_kwargs):
        raise RuntimeError("BT-27 induced planning failure")

    monkeypatch.setattr(presentation_generation, "execute_presentation_planning", _fail)
    with pytest.raises(RuntimeError, match="BT-27 induced planning failure"):
        client.post(
            f"/opportunities/{opportunity_id}/presentation-plan/generate",
            headers=headers,
            json={"framework_version_id": framework_version_id, "auto_continue": True},
        )

    planning_jobs = jobs_for(opportunity_id, "presentation_planning")
    assert len(planning_jobs) == 1
    failed = client.get(f"/jobs/{planning_jobs[0]['id']}", headers=headers)
    assert failed.status_code == 200, failed.text
    assert failed.json()["status"] == "FAILED"
    assert failed.json()["error"]["stage"] == JobStage.PRESENTATION_PLANNING.value
    assert failed.json()["error"]["message"]
    assert jobs_for(opportunity_id, "presentation_generation") == []

    # The confirmed Framework is untouched.
    framework = client.get(f"/opportunities/{opportunity_id}/framework", headers=headers)
    assert framework.status_code == 200, framework.text
    assert framework.json()["status"] == "confirmed"


def test_bt27_generation_failure_preserves_framework_and_plan(
    client: TestClient,
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opportunity_id, _ = create_opportunity_with_transcript(
        client,
        headers=headers,
        opportunity_name="BT-27 Generation Failure",
    )
    framework_version_id, _, _ = generate_and_confirm_framework(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
    )

    def _fail(*_args, **_kwargs):
        raise RuntimeError("BT-27 induced generation failure")

    monkeypatch.setattr(presentation_generation, "execute_presentation_generation", _fail)
    with pytest.raises(RuntimeError, match="BT-27 induced generation failure"):
        client.post(
            f"/opportunities/{opportunity_id}/presentation-plan/generate",
            headers=headers,
            json={"framework_version_id": framework_version_id, "auto_continue": True},
        )

    planning_jobs = jobs_for(opportunity_id, "presentation_planning")
    assert len(planning_jobs) == 1
    planning = client.get(f"/jobs/{planning_jobs[0]['id']}", headers=headers)
    assert planning.json()["status"] == "COMPLETED"

    generation_jobs = jobs_for(opportunity_id, "presentation_generation")
    assert len(generation_jobs) == 1
    failed = client.get(f"/jobs/{generation_jobs[0]['id']}", headers=headers)
    assert failed.status_code == 200, failed.text
    assert failed.json()["status"] == "FAILED"
    assert failed.json()["error"]["stage"] == JobStage.SLIDE_GENERATING.value

    # Framework and the persisted plan both survive a generation failure.
    framework = client.get(f"/opportunities/{opportunity_id}/framework", headers=headers)
    assert framework.json()["status"] == "confirmed"
    plan = client.get(f"/opportunities/{opportunity_id}/presentation-plan", headers=headers)
    assert plan.status_code == 200, plan.text
    assert plan.json()["framework_version_id"] == framework_version_id
