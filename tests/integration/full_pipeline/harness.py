"""AT-54: Full pipeline integration harness — upload → confirm → plan → slides → pptx."""

from __future__ import annotations

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
