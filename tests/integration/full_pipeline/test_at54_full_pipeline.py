"""AT-54: full pipeline integration test — upload → confirm → plan → slides → pptx."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from tests.integration.full_pipeline.harness import DEFAULT_FIXTURE_TRANSCRIPT, run_full_pipeline

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
HARNESS_PATH = Path(__file__).resolve().parent / "harness.py"


def _client() -> TestClient:
    return TestClient(create_app())


def _headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=USER_ID,
        email="owner@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def test_at54_fixture_transcript_exists() -> None:
    assert DEFAULT_FIXTURE_TRANSCRIPT.is_file()
    content = DEFAULT_FIXTURE_TRANSCRIPT.read_text(encoding="utf-8")
    assert len(content.strip()) > 0


def test_at54_harness_module_declares_pipeline_stages() -> None:
    source = HARNESS_PATH.read_text(encoding="utf-8")
    for stage in ("upload", "confirm", "plan", "slides", "pptx"):
        assert stage in source


def test_at54_fixture_transcript_runs_through_full_pipeline() -> None:
    client = _client()
    result = run_full_pipeline(client, headers=_headers())

    assert result.opportunity_id
    assert result.transcript_id
    assert result.framework_version_id
    assert result.presentation_plan_id
    assert result.presentation_id
    assert len(result.slide_ids) >= 1
    assert result.pptx_bytes.startswith(b"PK")

    plan = client.get(
        f"/opportunities/{result.opportunity_id}/presentation-plan",
        headers=_headers(),
    )
    assert plan.status_code == 200
    plan_json = plan.json()["plan_json"]
    assert isinstance(plan_json.get("slides"), list)
    assert len(plan_json["slides"]) >= 1

    slides = client.get(
        f"/presentations/{result.presentation_id}/slides",
        headers=_headers(),
    )
    assert slides.status_code == 200
    for slide in slides.json():
        assert slide.get("layout_id")
        assert slide.get("slide_spec")

    deck = client.get(
        f"/presentations/{result.presentation_id}/deck",
        headers=_headers(),
    )
    assert deck.status_code == 200
    assert deck.json()["pptx_download_url"].endswith("/download/pptx")
