from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.schemas.jobs import JobStage
from app.services.artifact_filing import (
    ArtifactFilingError,
    ArtifactFilingRequest,
    MemoryFilingMetadataStore,
    file_artifact,
)
from app.services.artifact_filing_stage import run_artifact_filing_for_presentation
from app.services.data.memory_store import get_memory_store
from app.services.deck_assets import deck_assets_root
from app.services.enterprise_repository import (
    LiveEnterpriseStore,
    build_enterprise_destination,
)
from app.services.job_retry import is_transient_failure
from app.services import job_service

USER_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
USER_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def _client() -> TestClient:
    return TestClient(create_app())


def _headers(user_id: UUID = USER_A, email: str = "owner@example.com") -> dict[str, str]:
    token = create_test_access_token(
        user_id=user_id,
        email=email,
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


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
    assert response.status_code == 201
    return response.json()["id"]


def _generate_presentation(client: TestClient, opportunity_id: str) -> dict:
    client.post(
        f"/opportunities/{opportunity_id}/framework/generate",
        headers=_headers(),
    )
    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200
    plan = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={},
    )
    assert plan.status_code == 202
    generated = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={"presentation_plan_id": plan.json()["presentation_plan_id"]},
    )
    assert generated.status_code == 202
    return generated.json()


class RecordingDestination:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def put(self, *, destination_path: str, content: bytes, content_type: str) -> str:
        self.calls.append(
            {
                "destination_path": destination_path,
                "content": content,
                "content_type": content_type,
            }
        )
        return f"sharepoint://pitch-factory/{destination_path}"


class FailingDestination:
    def put(self, *, destination_path: str, content: bytes, content_type: str) -> str:
        error = TimeoutError("repository timed out")
        error.code = "ENTERPRISE_REPOSITORY_TIMEOUT"  # type: ignore[attr-defined]
        error.retryable = True  # type: ignore[attr-defined]
        raise error


def _request(path: Path) -> ArtifactFilingRequest:
    return ArtifactFilingRequest(
        opportunity_id=uuid4(),
        presentation_id=uuid4(),
        presentation_version_id=uuid4(),
        artifact_kind="pitch-pptx",
        source_path=path,
        content_type=(
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ),
        approved_by=uuid4(),
        approved_at=datetime.now(UTC),
        framework_version_id=uuid4(),
        corpus_versions=("rates-2026-09-01", "staffing-2026-09-01"),
        provider="gamma",
    )


def test_filing_is_idempotent_and_keeps_approval_and_provenance(tmp_path: Path) -> None:
    artifact = tmp_path / "deck.pptx"
    artifact.write_bytes(b"PK fixture")
    request = _request(artifact)
    destination = RecordingDestination()
    metadata = MemoryFilingMetadataStore()

    first = file_artifact(request, destination=destination, metadata=metadata)
    second = file_artifact(request, destination=destination, metadata=metadata)

    assert first == second
    assert len(destination.calls) == 1
    assert first["status"] == "filed"
    assert first["approved_by"] == str(request.approved_by)
    assert first["framework_version_id"] == str(request.framework_version_id)
    assert first["corpus_versions"] == list(request.corpus_versions)
    assert first["provider"] == "gamma"
    assert first["repository_ref"].startswith("sharepoint://")


def test_transient_destination_failure_is_recorded_for_retry(tmp_path: Path) -> None:
    artifact = tmp_path / "deck.pdf"
    artifact.write_bytes(b"%PDF fixture")
    request = _request(artifact)
    metadata = MemoryFilingMetadataStore()

    with pytest.raises(ArtifactFilingError) as raised:
        file_artifact(request, destination=FailingDestination(), metadata=metadata)

    assert raised.value.code == "ENTERPRISE_REPOSITORY_TIMEOUT"
    assert raised.value.retryable is True
    record = next(iter(metadata.records.values()))
    assert record["status"] == "failed"
    assert record["error_retryable"] is True


def test_missing_artifact_is_not_retryable(tmp_path: Path) -> None:
    request = _request(tmp_path / "missing.pptx")

    with pytest.raises(ArtifactFilingError) as raised:
        file_artifact(
            request,
            destination=RecordingDestination(),
            metadata=MemoryFilingMetadataStore(),
        )

    assert raised.value.code == "ARTIFACT_NOT_FOUND"
    assert raised.value.retryable is False


def test_application_data_store_implements_filing_metadata_protocol(tmp_path: Path) -> None:
    artifact = tmp_path / "deck.pptx"
    artifact.write_bytes(b"PK fixture")

    record = file_artifact(
        _request(artifact),
        destination=RecordingDestination(),
        metadata=get_memory_store(),
    )

    assert get_memory_store().get_filing_record(record["idempotency_key"]) == record


def test_fixture_destination_persists_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(settings, "FILING_DESTINATION", "fixture")
    destination = build_enterprise_destination()
    ref = destination.put(
        destination_path="opportunities/demo/deck.pptx",
        content=b"PK fixture",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    stored = tmp_path / "enterprise" / "opportunities" / "demo" / "deck.pptx"
    assert stored.read_bytes() == b"PK fixture"
    assert ref == "fixture://enterprise/opportunities/demo/deck.pptx"


def test_live_destination_is_fail_closed_without_o2_credentials() -> None:
    destination = LiveEnterpriseStore(base_url="", token="", timeout_seconds=1)
    with pytest.raises(ArtifactFilingError) as raised:
        destination.put(
            destination_path="opportunities/demo/deck.pptx",
            content=b"PK",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    assert raised.value.code == "ENTERPRISE_REPOSITORY_NOT_CONFIGURED"
    assert raised.value.retryable is False


def test_enterprise_repository_retry_classification_extends_at57() -> None:
    timeout = ArtifactFilingError("ENTERPRISE_REPOSITORY_TIMEOUT", "timeout", retryable=True)
    unavailable = ArtifactFilingError(
        "ENTERPRISE_REPOSITORY_UNAVAILABLE",
        "down",
        retryable=True,
    )
    missing = ArtifactFilingError("ARTIFACT_NOT_FOUND", "missing", retryable=False)
    unconfigured = ArtifactFilingError(
        "ENTERPRISE_REPOSITORY_NOT_CONFIGURED",
        "O2 pending",
        retryable=False,
    )
    rejected = ArtifactFilingError("ENTERPRISE_REPOSITORY_REJECTED", "400", retryable=False)
    assert is_transient_failure(timeout) is True
    assert is_transient_failure(unavailable) is True
    assert is_transient_failure(missing) is False
    assert is_transient_failure(unconfigured) is False
    assert is_transient_failure(rejected) is False


def test_live_filing_without_o2_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "FILING_DESTINATION", "live")
    monkeypatch.setattr(settings, "ENTERPRISE_REPOSITORY_URL", "")
    monkeypatch.setattr(settings, "ENTERPRISE_REPOSITORY_TOKEN", "")
    client = TestClient(create_app(), raise_server_exceptions=False)
    opportunity_id = _create_opportunity(client)
    client.post(
        f"/opportunities/{opportunity_id}/framework/generate",
        headers=_headers(),
    )
    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200
    plan = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={},
    )
    assert plan.status_code == 202
    generated = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={"presentation_plan_id": plan.json()["presentation_plan_id"]},
    )
    assert generated.status_code in {202, 500}
    job = client.get(f"/opportunities/{opportunity_id}/jobs/latest", headers=_headers())
    assert job.status_code == 200
    body = job.json()
    assert body["status"] == "FAILED"
    assert body["error"]["code"] == "ENTERPRISE_REPOSITORY_NOT_CONFIGURED"
    assert body["error"]["retryable"] is False
    assert body["error"]["stage"] == JobStage.ARTIFACT_FILING.value


def test_generate_files_every_artifact_with_workflow_provenance_and_approval() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    generated = _generate_presentation(client, opportunity_id)

    listed = client.get(
        f"/opportunities/{opportunity_id}/filed-artifacts",
        headers=_headers(),
    )
    assert listed.status_code == 200
    rows = listed.json()
    assert {row["artifact_kind"] for row in rows} == {"pptx", "pdf"}
    assert {row["provider"] for row in rows} == {"internal"}
    assert all(row["status"] == "filed" for row in rows)
    assert all(row["opportunity_id"] == opportunity_id for row in rows)
    assert all(row["presentation_id"] == generated["presentation_id"] for row in rows)
    assert all(row["framework_version_id"] for row in rows)
    assert all(row["approved_by"] == str(USER_A) for row in rows)
    assert all(row["approved_at"] for row in rows)
    assert all(row["corpus_versions"] == ["borek-internal-dummy@2026.09.03"] for row in rows)
    assert all(str(row["repository_ref"]).startswith("fixture://enterprise/") for row in rows)
    for row in rows:
        relative = str(row["repository_ref"]).removeprefix("fixture://enterprise/")
        assert (deck_assets_root() / "enterprise" / Path(relative)).is_file()

    rerun = client.get(
        f"/opportunities/{opportunity_id}/filed-artifacts",
        headers=_headers(),
    )
    assert len(rerun.json()) == 2

    other = client.get(
        f"/opportunities/{opportunity_id}/filed-artifacts",
        headers=_headers(USER_B, "other@example.com"),
    )
    assert other.status_code == 404


def test_gamma_artifacts_are_filed_with_gamma_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    monkeypatch.setattr(settings, "GAMMA_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(settings, "FILING_DESTINATION", "fixture")
    client = _client()
    opportunity_id = _create_opportunity(client)
    _generate_presentation(client, opportunity_id)

    listed = client.get(
        f"/opportunities/{opportunity_id}/filed-artifacts",
        headers=_headers(),
    )
    assert listed.status_code == 200
    rows = listed.json()
    providers = {(row["provider"], row["artifact_kind"]) for row in rows}
    assert ("internal", "pptx") in providers
    assert ("internal", "pdf") in providers
    assert ("gamma", "pptx") in providers
    assert ("gamma", "pdf") in providers
    assert all(row["status"] == "filed" for row in rows)


def test_filing_stage_is_idempotent_for_the_same_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(settings, "FILING_DESTINATION", "fixture")
    client = _client()
    opportunity_id = _create_opportunity(client)
    generated = _generate_presentation(client, opportunity_id)
    store = get_memory_store()
    version = store.get_latest_presentation_version(
        presentation_id=UUID(generated["presentation_id"]),
        user_id=USER_A,
    )
    first = run_artifact_filing_for_presentation(
        store,
        presentation_id=generated["presentation_id"],
        user_id=USER_A,
        version=version,
        gamma_result={"skipped": True, "engine": "internal"},
    )
    second = run_artifact_filing_for_presentation(
        store,
        presentation_id=generated["presentation_id"],
        user_id=USER_A,
        version=version,
        gamma_result={"skipped": True, "engine": "internal"},
    )
    assert first["skipped"] is False
    assert first["filed"] == second["filed"]
    assert len(first["filed"]) == 2


def test_filing_stage_skips_when_fixture_generate_has_no_files() -> None:
    result = run_artifact_filing_for_presentation(
        get_memory_store(),
        presentation_id=uuid4(),
        user_id=USER_A,
        version={"id": uuid4()},
        gamma_result={"skipped": True},
    )
    assert result == {"skipped": True, "reason": "no_generated_artifacts", "filed": []}


def test_worker_invokes_automatic_filing_after_gamma() -> None:
    from app.worker import run_presentation_generation_task

    store = get_memory_store()
    presentation_id = uuid4()
    version_id = uuid4()
    job = job_service.create_job(
        uuid4(),
        "presentation_generation",
        presentation_id=presentation_id,
        enqueue={"user_id": str(USER_A), "presentation_id": str(presentation_id)},
        repository=store,
    )
    job_service.record_result_checkpoint(
        job.id,
        {"presentation_version_id": str(version_id)},
        repository=store,
    )
    job_service.fail_job(
        job.id,
        "LATE_STAGE_FAILED",
        "Late stage failed",
        JobStage.PREVIEW_RENDERING,
        True,
        repository=store,
    )
    job_service.resume_job(job.id, repository=store)
    checkpoint = ({"id": version_id, "storage_size_bytes": 123}, {"id": uuid4()})
    with (
        patch("app.services.data.build_worker_data_store", return_value=store),
        patch(
            "app.services.presentation_generation.load_presentation_generation_checkpoint",
            return_value=checkpoint,
        ),
        patch(
            "app.services.artifact_filing_stage.run_artifact_filing_for_presentation"
        ) as filing,
    ):
        filing.return_value = {"skipped": True, "reason": "no_generated_artifacts", "filed": []}
        run_presentation_generation_task.run(
            str(job.id),
            str(presentation_id),
            str(USER_A),
        )
    filing.assert_not_called()


def test_worker_files_when_resuming_from_artifact_filing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.worker import run_presentation_generation_task

    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(settings, "FILING_DESTINATION", "fixture")
    client = _client()
    opportunity_id = _create_opportunity(client)
    generated = _generate_presentation(client, opportunity_id)
    store = get_memory_store()
    presentation_id = UUID(generated["presentation_id"])
    version = store.get_latest_presentation_version(
        presentation_id=presentation_id,
        user_id=USER_A,
    )
    job = job_service.create_job(
        UUID(opportunity_id),
        "presentation_generation",
        presentation_id=presentation_id,
        enqueue={"user_id": str(USER_A), "presentation_id": str(presentation_id)},
        repository=store,
    )
    job_service.record_result_checkpoint(
        job.id,
        {
            "presentation_version_id": str(version["id"]),
            "gamma": {"skipped": True, "engine": "internal"},
        },
        repository=store,
    )
    job_service.fail_job(
        job.id,
        "ENTERPRISE_REPOSITORY_TIMEOUT",
        "repository timed out",
        JobStage.ARTIFACT_FILING,
        True,
        repository=store,
    )
    job_service.resume_job(job.id, repository=store)
    with (
        patch("app.services.data.build_worker_data_store", return_value=store),
        patch(
            "app.services.presentation_generation.execute_presentation_generation"
        ) as generate,
        patch(
            "app.services.presentation_generation.load_presentation_generation_checkpoint",
            return_value=(version, {"id": uuid4()}),
        ),
        patch("app.services.presentation_generation.render_presentation_version") as render,
    ):
        result = run_presentation_generation_task.run(
            str(job.id),
            str(presentation_id),
            str(USER_A),
        )
    generate.assert_not_called()
    render.assert_not_called()
    assert result["presentation_version_id"] == str(version["id"])
    completed = job_service.get_job(job.id, repository=store)
    assert completed is not None
    assert completed.status.value == "COMPLETED"
    assert completed.result_json["filing"]["skipped"] is False
    assert len(completed.result_json["filing"]["filed"]) == 2
