"""BT-28: PRESENTATION_ENGINE selects the deck-producing render stage."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import jsonschema
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth import create_test_access_token
from app.config import Settings, settings
from app.main import create_app
from app.schemas.jobs import JobStage, JobStatus
from app.services import job_service
from app.services.data.memory_store import get_memory_store
from app.services.deck_assets import resolve_gamma_artifact_path
from app.services.gamma_stage import (
    PresentationEngineConfigError,
    require_presentation_engine,
)
from services.gamma.contract import GammaAuthError, GammaTimeoutError
from services.gamma.payload import gamma_payload_schema

USER_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_LOCATION = ROOT / "packages" / "contracts" / "gamma_artifact_location.json"


def _client() -> TestClient:
    return TestClient(create_app())


def _headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=USER_A,
        email="owner@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": "Bearer " + token}


def _create_opportunity(client: TestClient) -> str:
    response = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Acme Corp",
            "opportunity_name": "Invoice Automation",
            "department": "Finance",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _generate_presentation(client: TestClient, opportunity_id: str) -> dict:
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200, confirm.text
    plan = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={},
    )
    assert plan.status_code == 202, plan.text
    generated = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={"presentation_plan_id": plan.json()["presentation_plan_id"]},
    )
    assert generated.status_code == 202, generated.text
    return generated.json()


def _run_worker_generation(
    *,
    store,
    presentation_id: uuid.UUID,
    version: dict,
    plan: dict,
    gamma_side_effect=None,
    gamma_return=None,
):
    from app.worker import run_presentation_generation_task

    job = job_service.create_job(
        uuid.uuid4(),
        "presentation_generation",
        presentation_id=presentation_id,
        enqueue={"user_id": str(USER_A), "presentation_id": str(presentation_id)},
        repository=store,
    )
    gamma_kwargs: dict = {}
    if gamma_side_effect is not None:
        gamma_kwargs["side_effect"] = gamma_side_effect
    elif gamma_return is not None:
        gamma_kwargs["return_value"] = gamma_return
    else:
        gamma_kwargs["return_value"] = {
            "skipped": False,
            "engine": "gamma",
            "artifacts": [],
        }
    with (
        patch("app.services.data.build_worker_data_store", return_value=store),
        patch(
            "app.services.presentation_generation.execute_presentation_generation",
            return_value=(version, plan),
        ) as generate,
        patch(
            "app.services.presentation_generation.load_presentation_generation_checkpoint",
            return_value=(version, plan),
        ),
        patch(
            "app.services.presentation_generation.render_presentation_version",
            return_value=version,
        ) as render,
        patch(
            "app.services.gamma_stage.run_gamma_stage_for_presentation",
            **gamma_kwargs,
        ) as gamma,
    ):
        try:
            result = run_presentation_generation_task.run(
                str(job.id),
                str(presentation_id),
                str(USER_A),
            )
        except Exception:
            result = None
    return job, generate, render, gamma, result


def test_invalid_presentation_engine_fails_closed() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, PRESENTATION_ENGINE="other")


def test_require_presentation_engine_rejects_unknown_value(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "powerpoint")
    with pytest.raises(PresentationEngineConfigError) as exc:
        require_presentation_engine()
    assert exc.value.code == "PRESENTATION_ENGINE_INVALID"
    assert exc.value.retryable is False


def test_internal_engine_runs_pptx_and_never_calls_gamma(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "internal")
    store = get_memory_store()
    presentation_id = uuid.uuid4()
    version = {"id": uuid.uuid4(), "storage_size_bytes": 12}
    plan = {"id": uuid.uuid4()}
    job, generate, render, gamma, result = _run_worker_generation(
        store=store,
        presentation_id=presentation_id,
        version=version,
        plan=plan,
    )
    generate.assert_called_once()
    render.assert_called_once()
    gamma.assert_not_called()
    assert result is not None
    completed = job_service.get_job(job.id, repository=store)
    assert completed is not None
    assert completed.status == JobStatus.COMPLETED
    assert completed.current_stage == JobStage.COMPLETED
    assert "gamma" not in (completed.result_json or {})


def test_gamma_engine_skips_internal_pptx_and_runs_gamma_stage(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    monkeypatch.setattr(settings, "GAMMA_EXECUTION_MODE", "fixture")
    store = get_memory_store()
    presentation_id = uuid.uuid4()
    version = {"id": uuid.uuid4(), "storage_size_bytes": 0}
    plan = {"id": uuid.uuid4()}
    job, generate, render, gamma, result = _run_worker_generation(
        store=store,
        presentation_id=presentation_id,
        version=version,
        plan=plan,
    )
    generate.assert_called_once()
    render.assert_not_called()
    gamma.assert_called_once()
    assert result is not None
    completed = job_service.get_job(job.id, repository=store)
    assert completed is not None
    assert completed.status == JobStatus.COMPLETED
    assert completed.result_json["gamma"]["skipped"] is False
    assert completed.result_json["gamma"]["engine"] == "gamma"


def test_switching_flag_off_restores_internal_renderer(monkeypatch) -> None:
    store = get_memory_store()
    presentation_id = uuid.uuid4()
    version = {"id": uuid.uuid4()}
    plan = {"id": uuid.uuid4()}
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    _, _, render_gamma, gamma_on, _ = _run_worker_generation(
        store=store,
        presentation_id=presentation_id,
        version=version,
        plan=plan,
    )
    render_gamma.assert_not_called()
    gamma_on.assert_called_once()

    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "internal")
    _, _, render_internal, gamma_off, _ = _run_worker_generation(
        store=store,
        presentation_id=uuid.uuid4(),
        version=version,
        plan=plan,
    )
    render_internal.assert_called_once()
    gamma_off.assert_not_called()


@pytest.mark.parametrize(
    ("error", "code", "retryable"),
    [
        (GammaTimeoutError(), "GAMMA_TIMEOUT", True),
        (GammaAuthError(), "GAMMA_AUTH", False),
    ],
)
def test_gamma_failure_stops_at_gamma_and_preserves_earlier_work(
    monkeypatch,
    error,
    code,
    retryable,
) -> None:
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    monkeypatch.setattr(settings, "GAMMA_EXECUTION_MODE", "fixture")
    store = get_memory_store()
    presentation_id = uuid.uuid4()
    version_id = uuid.uuid4()
    version = {"id": version_id}
    plan = {"id": uuid.uuid4()}
    job, generate, render, gamma, result = _run_worker_generation(
        store=store,
        presentation_id=presentation_id,
        version=version,
        plan=plan,
        gamma_side_effect=error,
    )
    assert result is None
    generate.assert_called_once()
    render.assert_not_called()
    assert gamma.call_count >= 1
    failed = job_service.get_job(job.id, repository=store)
    assert failed is not None
    assert failed.status == JobStatus.FAILED
    assert failed.failed_stage == JobStage.GAMMA_RENDERING
    assert failed.error_code == code
    assert failed.error_retryable is retryable
    assert failed.result_json["presentation_version_id"] == str(version_id)
    assert failed.result_json.get("gamma") is None
    response = job_service.job_to_response(failed)
    assert response.error is not None
    assert response.error.stage == JobStage.GAMMA_RENDERING
    assert response.error.retryable is retryable
    assert "engine" not in (response.model_dump(mode="json"))


def test_gamma_failure_does_not_fall_back_to_internal_renderer(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    store = get_memory_store()
    job, _, render, gamma, _ = _run_worker_generation(
        store=store,
        presentation_id=uuid.uuid4(),
        version={"id": uuid.uuid4()},
        plan={"id": uuid.uuid4()},
        gamma_side_effect=GammaTimeoutError(),
    )
    render.assert_not_called()
    gamma.assert_called()
    failed = job_service.get_job(job.id, repository=store)
    assert failed is not None
    assert failed.failed_stage == JobStage.GAMMA_RENDERING
    assert failed.status == JobStatus.FAILED


def test_resume_after_gamma_checkpoint_does_not_repeat_provider_work(monkeypatch) -> None:
    from app.worker import run_presentation_generation_task

    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    store = get_memory_store()
    presentation_id = uuid.uuid4()
    version_id = uuid.uuid4()
    version = {"id": version_id}
    plan = {"id": uuid.uuid4()}
    job = job_service.create_job(
        uuid.uuid4(),
        "presentation_generation",
        presentation_id=presentation_id,
        enqueue={"user_id": str(USER_A), "presentation_id": str(presentation_id)},
        repository=store,
    )
    job_service.record_result_checkpoint(
        job.id,
        {
            "presentation_version_id": str(version_id),
            "gamma": {"skipped": False, "engine": "gamma", "generation_id": "already-ran"},
        },
        repository=store,
    )
    job_service.fail_job(
        job.id,
        "ARTIFACT_FILING_FAILED",
        "archive failed",
        JobStage.ARTIFACT_FILING,
        True,
        repository=store,
    )
    job_service.resume_job(job.id, repository=store)
    with (
        patch("app.services.data.build_worker_data_store", return_value=store),
        patch("app.services.presentation_generation.execute_presentation_generation") as generate,
        patch(
            "app.services.presentation_generation.load_presentation_generation_checkpoint",
            return_value=(version, plan),
        ),
        patch("app.services.presentation_generation.render_presentation_version") as render,
        patch("app.services.gamma_stage.run_gamma_stage_for_presentation") as gamma,
        patch(
            "app.services.artifact_filing_stage.run_artifact_filing_for_presentation",
            return_value={"skipped": True, "filed": []},
        ),
    ):
        run_presentation_generation_task.run(
            str(job.id),
            str(presentation_id),
            str(USER_A),
        )
    generate.assert_not_called()
    render.assert_not_called()
    gamma.assert_not_called()


def test_gamma_path_consumes_es40_payload_and_persists_owned_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    monkeypatch.setattr(settings, "GAMMA_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    captured: dict = {}
    real_builder = __import__(
        "app.services.gamma_stage",
        fromlist=["build_gamma_content_payload"],
    ).build_gamma_content_payload

    def _capture_payload(*args, **kwargs):
        payload = real_builder(*args, **kwargs)
        captured["payload"] = payload
        return payload

    with (
        patch(
            "app.services.gamma_stage.build_gamma_content_payload",
            side_effect=_capture_payload,
        ),
        patch("app.services.presentation_generation.render_presentation_version") as render,
    ):
        client = _client()
        opportunity_id = _create_opportunity(client)
        generated = _generate_presentation(client, opportunity_id)

    render.assert_not_called()
    assert "payload" in captured
    jsonschema.validate(instance=captured["payload"], schema=gamma_payload_schema())
    assert captured["payload"]["schema_version"] == "1.0"

    store = get_memory_store()
    version = store.get_latest_presentation_version(
        presentation_id=uuid.UUID(generated["presentation_id"]),
        user_id=USER_A,
    )
    pptx = resolve_gamma_artifact_path(
        opportunity_id=opportunity_id,
        version_id=version["id"],
        kind="pptx",
    )
    pdf = resolve_gamma_artifact_path(
        opportunity_id=opportunity_id,
        version_id=version["id"],
        kind="pdf",
    )
    assert pptx is not None and pptx.is_file()
    assert pdf is not None and pdf.is_file()
    location = json.loads(ARTIFACT_LOCATION.read_text(encoding="utf-8"))
    expected_prefix = location["relative_directory"].format(
        opportunity_id=opportunity_id,
        presentation_version_id=str(version["id"]),
    )
    assert str(pptx.as_posix()).endswith(
        expected_prefix.rstrip("/") + "/" + pptx.name
    ) or expected_prefix.rstrip("/") in str(pptx.as_posix())

    deck = client.get(
        f"/presentations/{generated['presentation_id']}/deck",
        headers=_headers(),
    )
    assert deck.status_code == 200, deck.text
    body = deck.json()
    assert "engine" not in body
    assert "gamma" not in deck.text.lower()
    assert body["pptx_download_url"] == (
        f"/presentations/{generated['presentation_id']}/download/pptx"
    )
    assert body["pdf_download_url"] == (
        f"/presentations/{generated['presentation_id']}/download/pdf"
    )

    downloaded = client.get(body["pptx_download_url"], headers=_headers())
    assert downloaded.status_code == 200
    assert downloaded.content == pptx.read_bytes()
    downloaded_pdf = client.get(body["pdf_download_url"], headers=_headers())
    assert downloaded_pdf.status_code == 200
    assert downloaded_pdf.content == pdf.read_bytes()

    completed = job_service.get_job(uuid.UUID(generated["job_id"]), repository=store)
    assert completed is not None
    assert completed.status == JobStatus.COMPLETED
    assert completed.result_json["gamma"]["skipped"] is False


def test_internal_engine_api_path_does_not_call_gamma_provider(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "internal")
    with (
        patch("app.services.presentation_generation.render_presentation_version") as render,
        patch("services.gamma.fixture_client.FixtureGammaClient.generate") as generate,
    ):
        render.side_effect = lambda *args, **kwargs: kwargs["version"]
        client = _client()
        opportunity_id = _create_opportunity(client)
        generated = _generate_presentation(client, opportunity_id)

    render.assert_called()
    generate.assert_not_called()
    store = get_memory_store()
    completed = job_service.get_job(uuid.UUID(generated["job_id"]), repository=store)
    assert completed is not None
    assert completed.status == JobStatus.COMPLETED
    assert completed.result_json.get("gamma", {}).get("skipped", True) is True


def test_gamma_artifact_location_contract_matches_persisted_keys() -> None:
    contract = json.loads(ARTIFACT_LOCATION.read_text(encoding="utf-8"))
    assert contract["schema_version"] == "1.0"
    assert contract["consumer"] == "JJ-30"
    assert contract["relative_directory"] == "gamma/{opportunity_id}/{presentation_version_id}/"
    assert contract["filename_pattern"] == "{generation_id}.{format}"
    assert set(contract["formats"]) == {"pptx", "pdf"}
    assert (
        contract["storage_key_pattern"]
        == "gamma/{opportunity_id}/{presentation_version_id}/{generation_id}.{format}"
    )
