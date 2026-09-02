"""AT-54: Full pipeline integration harness — upload → confirm → plan → slides → pptx.

BT-27 adds the automated variant: the same flow driven only by human Framework
approval, where the backend owns the Plan → Presentation continuation.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE_TRANSCRIPT = ROOT / "tests" / "fixtures" / "transcripts" / "discovery_call.minimal.txt"


@dataclass(frozen=True)
class FullPipelineResult:
    opportunity_id: str
    transcript_id: str
    framework_version_id: str
    presentation_plan_id: str
    presentation_id: str
    slide_ids: tuple[str, ...]
    pptx_bytes: bytes


@dataclass(frozen=True)
class AutomatedPipelineResult:
    """BT-25/BT-27: what the automated build produced, and how it got there."""

    opportunity_id: str
    transcript_id: str
    framework_version_id: str
    framework_job_id: str
    framework_stages: tuple[str, ...]
    planning_job_id: str
    planning_reused: bool
    presentation_plan_id: str
    generation_job_id: str
    generation_stages: tuple[str, ...]
    presentation_id: str
    presentation_version_id: str
    slide_ids: tuple[str, ...]
    pptx_bytes: bytes
    generation_found_via_at56: bool


@contextmanager
def record_job_stages() -> Iterator[list[tuple[str, str]]]:
    """Capture the JobStage transitions the production workers really emit."""
    from app.services import job_service

    recorded: list[tuple[str, str]] = []
    original = job_service.ensure_stage

    def _recording_ensure_stage(job_id, stage, *args, **kwargs):
        recorded.append((str(job_id), str(getattr(stage, "value", stage))))
        return original(job_id, stage, *args, **kwargs)

    job_service.ensure_stage = _recording_ensure_stage
    try:
        yield recorded
    finally:
        job_service.ensure_stage = original


def stages_for_job(recorded: list[tuple[str, str]], job_id: str) -> tuple[str, ...]:
    """Ordered stages for one job, collapsing repeated ensure_stage calls."""
    stages: list[str] = []
    for recorded_job_id, stage in recorded:
        if recorded_job_id != str(job_id):
            continue
        if not stages or stages[-1] != stage:
            stages.append(stage)
    return tuple(stages)


def get_active_job(
    client: TestClient,
    *,
    headers: dict[str, str],
    opportunity_id: str,
    stage_group: str,
) -> dict | None:
    """AT-56 reconnect: look a job up knowing only the opportunity."""
    response = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=headers,
        params={"stage_group": stage_group},
    )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise AssertionError(f"active job lookup failed: {response.status_code} {response.text}")
    return response.json()


def _find_backend_generation_job(
    client: TestClient,
    *,
    headers: dict[str, str],
    opportunity_id: str,
    timeout_seconds: float = 30,
) -> tuple[str, bool]:
    """Locate the generation job the backend started, never requesting one."""
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        active = get_active_job(
            client,
            headers=headers,
            opportunity_id=opportunity_id,
            stage_group="presentation",
        )
        if active is not None and active["job_type"] == "presentation_generation":
            return str(active["job_id"]), True
        if active is not None and active["status"] in {"COMPLETED", "FAILED"}:
            break
        sleep(0.05)

    # Under Celery eager mode the whole chain finishes inside the planning
    # request, so AT-56 may answer with the equally terminal planning job.
    # Read the store directly: what matters here is that the backend created a
    # generation job without the client ever requesting one.
    from uuid import UUID

    from app.services.data.memory_store import get_memory_store

    rows = [
        row
        for row in get_memory_store().generation_jobs.values()
        if row.get("opportunity_id") == UUID(opportunity_id)
        and row.get("job_type") == "presentation_generation"
    ]
    if not rows:
        raise AssertionError(
            f"backend started no presentation_generation job for opportunity {opportunity_id}"
        )
    if len(rows) > 1:
        raise AssertionError(
            f"expected one backend generation job, found {len(rows)} for {opportunity_id}"
        )
    return str(rows[0]["id"]), False


def _wait_for_job(
    client: TestClient,
    *,
    headers: dict[str, str],
    job_id: str,
    timeout_seconds: float = 30,
) -> dict:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        response = client.get(f"/jobs/{job_id}", headers=headers)
        if response.status_code != 200:
            raise AssertionError(f"job status failed: {response.status_code} {response.text}")
        job = response.json()
        if job["status"] == "COMPLETED":
            return job
        if job["status"] == "FAILED":
            raise AssertionError(f"generation job failed: {job['error']}")
        sleep(0.05)
    raise AssertionError(f"generation job {job_id} did not complete")


def run_full_pipeline(
    client: TestClient,
    *,
    headers: dict[str, str],
    transcript_path: Path = DEFAULT_FIXTURE_TRANSCRIPT,
) -> FullPipelineResult:
    """Drive the API through upload → confirm → plan → slides → pptx."""
    transcript_bytes = transcript_path.read_bytes()

    opportunity = client.post(
        "/opportunities",
        headers=headers,
        json={
            "client_name": "Pipeline Test Corp",
            "opportunity_name": "Full Pipeline Harness",
            "department": "Finance",
            "language": "en",
        },
    )
    if opportunity.status_code != 201:
        raise AssertionError(f"create opportunity failed: {opportunity.status_code} {opportunity.text}")
    opportunity_id = opportunity.json()["id"]

    upload = client.post(
        f"/opportunities/{opportunity_id}/transcripts",
        headers=headers,
        files={"file": (transcript_path.name, transcript_bytes, "text/plain")},
    )
    if upload.status_code != 201:
        raise AssertionError(f"upload transcript failed: {upload.status_code} {upload.text}")
    transcript_id = upload.json()["transcript"]["id"]

    generate_framework = client.post(
        f"/opportunities/{opportunity_id}/framework/generate",
        headers=headers,
    )
    if generate_framework.status_code != 202:
        raise AssertionError(
            f"framework generate failed: {generate_framework.status_code} {generate_framework.text}"
        )
    framework_version_id = generate_framework.json()["framework_version_id"]
    _wait_for_job(
        client,
        headers=headers,
        job_id=generate_framework.json()["job_id"],
    )

    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=headers,
        json={"framework_version_id": framework_version_id},
    )
    if confirm.status_code != 200:
        raise AssertionError(f"framework confirm failed: {confirm.status_code} {confirm.text}")
    if confirm.json()["status"] != "confirmed":
        raise AssertionError("framework must be confirmed before planning")

    plan = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=headers,
        json={"framework_version_id": framework_version_id},
    )
    if plan.status_code != 202:
        raise AssertionError(f"plan generate failed: {plan.status_code} {plan.text}")
    presentation_plan_id = plan.json()["presentation_plan_id"]
    _wait_for_job(client, headers=headers, job_id=plan.json()["job_id"])

    presentation = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=headers,
        json={
            "framework_version_id": framework_version_id,
            "presentation_plan_id": presentation_plan_id,
        },
    )
    if presentation.status_code != 202:
        raise AssertionError(
            f"presentation generate failed: {presentation.status_code} {presentation.text}"
        )
    presentation_id = presentation.json()["presentation_id"]
    _wait_for_job(client, headers=headers, job_id=presentation.json()["job_id"])

    slides = client.get(f"/presentations/{presentation_id}/slides", headers=headers)
    if slides.status_code != 200:
        raise AssertionError(f"list slides failed: {slides.status_code} {slides.text}")
    slide_rows = slides.json()
    if not slide_rows:
        raise AssertionError("presentation must contain at least one slide")

    pptx = client.get(
        f"/presentations/{presentation_id}/download/pptx",
        headers=headers,
    )
    if pptx.status_code != 200:
        raise AssertionError(f"pptx download failed: {pptx.status_code} {pptx.text}")
    pptx_bytes = pptx.content
    if not pptx_bytes:
        raise AssertionError("pptx download returned empty body")

    return FullPipelineResult(
        opportunity_id=opportunity_id,
        transcript_id=transcript_id,
        framework_version_id=framework_version_id,
        presentation_plan_id=presentation_plan_id,
        presentation_id=presentation_id,
        slide_ids=tuple(row["id"] for row in slide_rows),
        pptx_bytes=pptx_bytes,
    )


def create_opportunity_with_transcript(
    client: TestClient,
    *,
    headers: dict[str, str],
    transcript_path: Path = DEFAULT_FIXTURE_TRANSCRIPT,
    client_name: str = "Pipeline Test Corp",
    opportunity_name: str = "Automated Pipeline Harness",
) -> tuple[str, str]:
    opportunity = client.post(
        "/opportunities",
        headers=headers,
        json={
            "client_name": client_name,
            "opportunity_name": opportunity_name,
            "department": "Finance",
            "language": "en",
        },
    )
    if opportunity.status_code != 201:
        raise AssertionError(f"create opportunity failed: {opportunity.status_code} {opportunity.text}")
    opportunity_id = opportunity.json()["id"]

    upload = client.post(
        f"/opportunities/{opportunity_id}/transcripts",
        headers=headers,
        files={"file": (transcript_path.name, transcript_path.read_bytes(), "text/plain")},
    )
    if upload.status_code != 201:
        raise AssertionError(f"upload transcript failed: {upload.status_code} {upload.text}")
    return opportunity_id, upload.json()["transcript"]["id"]


def generate_and_confirm_framework(
    client: TestClient,
    *,
    headers: dict[str, str],
    opportunity_id: str,
) -> tuple[str, str, tuple[str, ...]]:
    """Framework generation plus the mandatory human confirmation."""
    with record_job_stages() as recorded:
        generate = client.post(
            f"/opportunities/{opportunity_id}/framework/generate",
            headers=headers,
        )
        if generate.status_code != 202:
            raise AssertionError(f"framework generate failed: {generate.status_code} {generate.text}")
        framework_version_id = generate.json()["framework_version_id"]
        framework_job_id = generate.json()["job_id"]
        _wait_for_job(client, headers=headers, job_id=framework_job_id)
    framework_stages = stages_for_job(recorded, framework_job_id)

    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=headers,
        json={"framework_version_id": framework_version_id},
    )
    if confirm.status_code != 200:
        raise AssertionError(f"framework confirm failed: {confirm.status_code} {confirm.text}")
    if confirm.json()["status"] != "confirmed":
        raise AssertionError("framework must be confirmed before planning")
    return framework_version_id, framework_job_id, framework_stages


def run_automated_pipeline(
    client: TestClient,
    *,
    headers: dict[str, str],
    transcript_path: Path = DEFAULT_FIXTURE_TRANSCRIPT,
) -> AutomatedPipelineResult:
    """BT-27: upload → framework → human approval → automated deck.

    The only presentation request this makes is the plan request carrying
    ``auto_continue``. Presentation generation is never requested: the backend
    owns that step (BT-25), and this harness only observes it.
    """
    opportunity_id, transcript_id = create_opportunity_with_transcript(
        client,
        headers=headers,
        transcript_path=transcript_path,
    )
    framework_version_id, framework_job_id, framework_stages = generate_and_confirm_framework(
        client,
        headers=headers,
        opportunity_id=opportunity_id,
    )

    with record_job_stages() as recorded:
        plan = client.post(
            f"/opportunities/{opportunity_id}/presentation-plan/generate",
            headers=headers,
            json={
                "framework_version_id": framework_version_id,
                "auto_continue": True,
            },
        )
        if plan.status_code != 202:
            raise AssertionError(f"plan generate failed: {plan.status_code} {plan.text}")
        planning_job_id = str(plan.json()["job_id"])
        presentation_plan_id = str(plan.json()["presentation_plan_id"])
        planning_reused = bool(plan.json()["is_existing_job"])
        _wait_for_job(client, headers=headers, job_id=planning_job_id)

        generation_job_id, found_via_at56 = _find_backend_generation_job(
            client,
            headers=headers,
            opportunity_id=opportunity_id,
        )
        generation_job = _wait_for_job(client, headers=headers, job_id=generation_job_id)
    generation_stages = stages_for_job(recorded, generation_job_id)

    generation_result = generation_job.get("result") or {}
    presentation_id = generation_result.get("presentation_id")
    presentation_version_id = generation_result.get("presentation_version_id")
    if not presentation_id or not presentation_version_id:
        raise AssertionError(f"generation job result is incomplete: {generation_result}")

    slides = client.get(f"/presentations/{presentation_id}/slides", headers=headers)
    if slides.status_code != 200:
        raise AssertionError(f"list slides failed: {slides.status_code} {slides.text}")
    slide_rows = slides.json()
    if not slide_rows:
        raise AssertionError("presentation must contain at least one slide")

    pptx = client.get(f"/presentations/{presentation_id}/download/pptx", headers=headers)
    if pptx.status_code != 200:
        raise AssertionError(f"pptx download failed: {pptx.status_code} {pptx.text}")
    if not pptx.content:
        raise AssertionError("pptx download returned empty body")

    return AutomatedPipelineResult(
        opportunity_id=opportunity_id,
        transcript_id=transcript_id,
        framework_version_id=framework_version_id,
        framework_job_id=framework_job_id,
        framework_stages=framework_stages,
        planning_job_id=planning_job_id,
        planning_reused=planning_reused,
        presentation_plan_id=presentation_plan_id,
        generation_job_id=generation_job_id,
        generation_stages=generation_stages,
        presentation_id=str(presentation_id),
        presentation_version_id=str(presentation_version_id),
        slide_ids=tuple(row["id"] for row in slide_rows),
        pptx_bytes=pptx.content,
        generation_found_via_at56=found_via_at56,
    )
