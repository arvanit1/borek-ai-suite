"""BT-33 Phase 2 — follow-up pipeline, persistence, mailbox, egress."""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.schemas.jobs import JobStage, JobStatus
from app.services import job_service
from app.services.data.memory_store import get_memory_store, reset_memory_store
from app.services.followup_pipeline import (
    FOLLOWUP_JOB_TYPE,
    enqueue_followup_generate,
    run_followup_generation,
)
from app.services.followup_rollout import FollowupRolloutError
from services.followup.extraction import load_followup_fixture
from services.mailbox.fixture_client import reset_fixture_mailbox_store
from services.security.egress_audit import list_egress_decisions, reset_egress_decisions
from services.security.egress_policy import EgressBlockedError, reset_egress_policy_cache

ROOT = Path(__file__).resolve().parents[3]
TRANSCRIPT_PATH = ROOT / "packages/contracts/fixtures/followup_extraction/workshop_clear.transcript.txt"
FIXTURE_PROJECT = "fixture-acme-invoice"
USER_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
USER_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


@pytest.fixture(autouse=True)
def _reset_stores() -> None:
    reset_memory_store()
    reset_fixture_mailbox_store()
    reset_egress_decisions()
    reset_egress_policy_cache()
    yield
    reset_egress_decisions()
    reset_egress_policy_cache()


@pytest.fixture
def allow_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "FOLLOWUP_ALLOWED_PROJECT_KEYS", FIXTURE_PROJECT)
    monkeypatch.setattr(settings, "API_DATA_BACKEND", "memory")
    monkeypatch.setattr(settings, "MAILBOX_EXECUTION_MODE", "fixture")


def _client() -> TestClient:
    return TestClient(create_app())


def _headers(user_id: uuid.UUID = USER_A, email: str = "owner@example.com") -> dict[str, str]:
    token = create_test_access_token(
        user_id=user_id,
        email=email,
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def _statics() -> dict:
    return {
        "project_name": "Acme Invoice Automation",
        "salutation_style": "informal",
        "recipient_first_name": "Markus",
        "time_reference": "today",
        "sender_name": "Lena Hoffmann",
        "sender_role": "Delivery Lead",
    }


def _fixture_complete(_system: str, _user: str, _schema: dict) -> dict:
    _, expected, _ = load_followup_fixture("workshop_clear")
    return expected


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


def _seed_transcript(store, opportunity_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
    content = TRANSCRIPT_PATH.read_bytes()
    row = store.create_transcript(
        opportunity_id=opportunity_id,
        user_id=user_id,
        file_name="workshop_clear.transcript.txt",
        mime_type="text/plain",
        storage_path="fixture/workshop_clear.transcript.txt",
        conversation_id="fixture-workshop",
        content=content,
        sections=[{"speaker": "Lena Hoffmann", "text": "workshop"}],
    )
    return row["id"]


def _run_pipeline(
    store,
    *,
    opportunity_id: uuid.UUID,
    user_id: uuid.UUID = USER_A,
    **kwargs,
):
    transcript_id = _seed_transcript(store, opportunity_id, user_id)
    job = job_service.create_job(
        opportunity_id,
        FOLLOWUP_JOB_TYPE,
        enqueue={
            "user_id": str(user_id),
            "transcript_id": str(transcript_id),
            "project_key": FIXTURE_PROJECT,
            "project_statics": _statics(),
            "meeting_owner_email": "owner@example.com",
            "calendar_meeting_date": "11.09.2026",
            "client_recipient_email": "client@acme.example",
        },
        repository=store,
    )
    return run_followup_generation(
        store,
        job_id=job.id,
        opportunity_id=opportunity_id,
        user_id=user_id,
        extraction_complete=_fixture_complete,
        **kwargs,
    )


def test_full_fixture_pipeline_reaches_draft_ready(allow_project) -> None:
    store = get_memory_store()
    opportunity_id = uuid.uuid4()
    store.create_opportunity(
        user_id=USER_A,
        client_name="Acme",
        opportunity_name="Invoice",
        department="Finance",
        language="en",
    )
    opp = next(iter(store.opportunities.values()))
    job = _run_pipeline(store, opportunity_id=opp["id"])
    assert job.status == JobStatus.COMPLETED
    draft = store.get_followup_draft(opportunity_id=opp["id"], user_id=USER_A)
    assert draft is not None
    assert draft["status"] == "draft"
    assert draft["provider_draft_id"]
    assert job.result_json["followup"]["review_status"] == "pending"


def test_stage_sequence_recorded(allow_project) -> None:
    store = get_memory_store()
    opportunity_id = uuid.uuid4()
    store.create_opportunity(
        user_id=USER_A,
        client_name="Acme",
        opportunity_name="Invoice",
        department="Finance",
        language="en",
    )
    opp = next(iter(store.opportunities.values()))
    transcript_id = _seed_transcript(store, opp["id"], USER_A)
    job = job_service.create_job(
        opp["id"],
        FOLLOWUP_JOB_TYPE,
        enqueue={
            "user_id": str(USER_A),
            "transcript_id": str(transcript_id),
            "project_key": FIXTURE_PROJECT,
            "project_statics": _statics(),
            "meeting_owner_email": "owner@example.com",
        },
        repository=store,
    )
    stages: list[str] = []

    original_ensure = job_service.ensure_stage

    def tracking_ensure(job_id, stage, *, repository=None):
        stages.append(stage.value)
        return original_ensure(job_id, stage, repository=repository)

    with patch("app.services.followup_pipeline.job_service.ensure_stage", side_effect=tracking_ensure):
        run_followup_generation(
            store,
            job_id=job.id,
            opportunity_id=opp["id"],
            user_id=USER_A,
            extraction_complete=_fixture_complete,
        )
    assert stages == [
        JobStage.FOLLOWUP_EXTRACTION.value,
        JobStage.FOLLOWUP_RENDERING.value,
        JobStage.FOLLOWUP_DRAFT.value,
    ]


def test_extraction_failure_stage(allow_project) -> None:
    store = get_memory_store()
    store.create_opportunity(
        user_id=USER_A,
        client_name="Acme",
        opportunity_name="Invoice",
        department="Finance",
        language="en",
    )
    opp = next(iter(store.opportunities.values()))
    job = _run_pipeline(
        store,
        opportunity_id=opp["id"],
        force_fail_stage=JobStage.FOLLOWUP_EXTRACTION,
    )
    assert job.status == JobStatus.FAILED
    assert job.failed_stage == JobStage.FOLLOWUP_EXTRACTION


def test_rendering_failure_preserves_extraction(allow_project) -> None:
    store = get_memory_store()
    store.create_opportunity(
        user_id=USER_A,
        client_name="Acme",
        opportunity_name="Invoice",
        department="Finance",
        language="en",
    )
    opp = next(iter(store.opportunities.values()))
    job = _run_pipeline(
        store,
        opportunity_id=opp["id"],
        force_fail_stage=JobStage.FOLLOWUP_RENDERING,
    )
    assert job.status == JobStatus.FAILED
    assert job.failed_stage == JobStage.FOLLOWUP_RENDERING
    assert job.result_json["followup"]["extraction"]


def test_mailbox_failure_preserves_rendered_draft(allow_project) -> None:
    store = get_memory_store()
    store.create_opportunity(
        user_id=USER_A,
        client_name="Acme",
        opportunity_name="Invoice",
        department="Finance",
        language="en",
    )
    opp = next(iter(store.opportunities.values()))
    job = _run_pipeline(
        store,
        opportunity_id=opp["id"],
        force_fail_stage=JobStage.FOLLOWUP_DRAFT,
    )
    assert job.status == JobStatus.FAILED
    assert job.failed_stage == JobStage.FOLLOWUP_DRAFT
    assert job.result_json["followup"]["rendered"]
    draft = store.get_followup_draft(opportunity_id=opp["id"], user_id=USER_A)
    assert draft is not None


def test_resume_from_rendering_without_re_extraction(allow_project) -> None:
    store = get_memory_store()
    store.create_opportunity(
        user_id=USER_A,
        client_name="Acme",
        opportunity_name="Invoice",
        department="Finance",
        language="en",
    )
    opp = next(iter(store.opportunities.values()))
    failed = _run_pipeline(
        store,
        opportunity_id=opp["id"],
        force_fail_stage=JobStage.FOLLOWUP_RENDERING,
    )
    calls = {"count": 0}

    def counting_complete(*args, **kwargs):
        calls["count"] += 1
        return _fixture_complete(*args, **kwargs)

    resumed = job_service.resume_job(failed.id, repository=store)
    completed = run_followup_generation(
        store,
        job_id=resumed.id,
        opportunity_id=opp["id"],
        user_id=USER_A,
        extraction_complete=counting_complete,
    )
    assert completed.status == JobStatus.COMPLETED
    assert calls["count"] == 0


def test_resume_from_drafting_without_re_render(allow_project) -> None:
    store = get_memory_store()
    store.create_opportunity(
        user_id=USER_A,
        client_name="Acme",
        opportunity_name="Invoice",
        department="Finance",
        language="en",
    )
    opp = next(iter(store.opportunities.values()))
    failed = _run_pipeline(
        store,
        opportunity_id=opp["id"],
        force_fail_stage=JobStage.FOLLOWUP_DRAFT,
    )
    render_calls = {"count": 0}
    original_render = __import__(
        "services.followup.rendering", fromlist=["render_followup_draft"]
    ).render_followup_draft

    def counting_render(*args, **kwargs):
        render_calls["count"] += 1
        return original_render(*args, **kwargs)

    resumed = job_service.resume_job(failed.id, repository=store)
    with patch("app.services.followup_pipeline.render_followup_draft", side_effect=counting_render):
        completed = run_followup_generation(
            store,
            job_id=resumed.id,
            opportunity_id=opp["id"],
            user_id=USER_A,
            extraction_complete=_fixture_complete,
        )
    assert completed.status == JobStatus.COMPLETED
    assert render_calls["count"] == 0


def test_duplicate_trigger_reuses_one_job(allow_project) -> None:
    store = get_memory_store()
    store.create_opportunity(
        user_id=USER_A,
        client_name="Acme",
        opportunity_name="Invoice",
        department="Finance",
        language="en",
    )
    opp = next(iter(store.opportunities.values()))
    transcript_id = _seed_transcript(store, opp["id"], USER_A)
    running = job_service.create_job(
        opp["id"],
        FOLLOWUP_JOB_TYPE,
        enqueue={
            "user_id": str(USER_A),
            "transcript_id": str(transcript_id),
            "project_key": FIXTURE_PROJECT,
            "project_statics": _statics(),
            "meeting_owner_email": "owner@example.com",
        },
        repository=store,
    )
    job_service.ensure_stage(running.id, JobStage.FOLLOWUP_EXTRACTION, repository=store)
    first, job_a, existing_a = enqueue_followup_generate(
        store,
        opportunity_id=opp["id"],
        user_id=USER_A,
        transcript_id=transcript_id,
        project_key=FIXTURE_PROJECT,
        project_statics=_statics(),
        meeting_owner_email="owner@example.com",
    )
    second, job_b, existing_b = enqueue_followup_generate(
        store,
        opportunity_id=opp["id"],
        user_id=USER_A,
        transcript_id=transcript_id,
        project_key=FIXTURE_PROJECT,
        project_statics=_statics(),
        meeting_owner_email="owner@example.com",
    )
    assert existing_a is True
    assert existing_b is True
    assert job_a.id == running.id
    assert job_b.id == running.id


def test_duplicate_draft_retry_reuses_provider_draft(allow_project) -> None:
    from services.mailbox import FixtureMailboxClient, MailboxDraftRequest, mailbox_draft_idempotency_key

    client = FixtureMailboxClient()
    key = mailbox_draft_idempotency_key(
        opportunity_id=str(uuid.uuid4()),
        followup_job_id=str(uuid.uuid4()),
    )
    request = MailboxDraftRequest(
        idempotency_key=key,
        opportunity_id=str(uuid.uuid4()),
        followup_job_id=str(uuid.uuid4()),
        meeting_owner_email="owner@example.com",
        subject="Subject",
        body="Body",
        reviewed=False,
    )
    first = client.create_draft(request)
    second = client.create_draft(request)
    assert first.provider_draft_id == second.provider_draft_id
    assert second.reused_existing is True


def test_unreviewed_client_recipient_refused(allow_project) -> None:
    from services.mailbox import FixtureMailboxClient, MailboxDraftRequest

    client = FixtureMailboxClient()
    with pytest.raises(Exception) as exc:
        client.create_draft(
            MailboxDraftRequest(
                idempotency_key="test-unreviewed",
                opportunity_id=str(uuid.uuid4()),
                followup_job_id=str(uuid.uuid4()),
                meeting_owner_email="owner@example.com",
                subject="Subject",
                body="Body",
                reviewed=False,
                client_recipient_email="client@acme.example",
            )
        )
    assert exc.value.code == "FOLLOWUP_CLIENT_UNREVIEWED"


def test_send_attempt_refused(allow_project) -> None:
    client = _client()
    response = client.post(
        f"/opportunities/{uuid.uuid4()}/followup/send",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FOLLOWUP_SEND_FORBIDDEN"


def test_review_does_not_send(allow_project) -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    store = get_memory_store()
    transcript_id = _seed_transcript(store, uuid.UUID(opportunity_id), USER_A)
    with patch(
        "app.services.followup_pipeline.extract_followup",
        side_effect=lambda *a, **k: _fixture_complete("", "", {}),
    ):
        client.post(
            f"/opportunities/{opportunity_id}/followup/generate",
            headers=_headers(),
            json={
                "transcript_id": str(transcript_id),
                "project_key": FIXTURE_PROJECT,
                "project_statics": _statics(),
                "meeting_owner_email": "owner@example.com",
            },
        )
    confirm = client.post(
        f"/opportunities/{opportunity_id}/followup/review/confirm",
        headers=_headers(),
        params={"client_recipient_email": "client@acme.example"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["draft"]["status"] == "reviewed"


def test_review_preserves_edited_subject_body(allow_project) -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    store = get_memory_store()
    transcript_id = _seed_transcript(store, uuid.UUID(opportunity_id), USER_A)
    with patch(
        "app.services.followup_pipeline.extract_followup",
        side_effect=lambda *a, **k: _fixture_complete("", "", {}),
    ):
        client.post(
            f"/opportunities/{opportunity_id}/followup/generate",
            headers=_headers(),
            json={
                "transcript_id": str(transcript_id),
                "project_key": FIXTURE_PROJECT,
                "project_statics": _statics(),
                "meeting_owner_email": "owner@example.com",
            },
        )
    edited_subject = "Edited subject line"
    edited_body = "Edited body content"
    save = client.patch(
        f"/opportunities/{opportunity_id}/followup/draft",
        headers=_headers(),
        json={"subject": edited_subject, "body": edited_body},
    )
    assert save.status_code == 200
    confirm = client.post(
        f"/opportunities/{opportunity_id}/followup/review/confirm",
        headers=_headers(),
    )
    assert confirm.status_code == 200
    assert confirm.json()["draft"]["subject"] == edited_subject
    assert confirm.json()["draft"]["body"] == edited_body


def test_unlisted_project_refused_before_extraction(allow_project, monkeypatch) -> None:
    monkeypatch.setattr(settings, "FOLLOWUP_ALLOWED_PROJECT_KEYS", "")
    client = _client()
    opportunity_id = _create_opportunity(client)
    store = get_memory_store()
    transcript_id = _seed_transcript(store, uuid.UUID(opportunity_id), USER_A)
    response = client.post(
        f"/opportunities/{opportunity_id}/followup/generate",
        headers=_headers(),
        json={
            "transcript_id": str(transcript_id),
            "project_key": FIXTURE_PROJECT,
            "project_statics": _statics(),
            "meeting_owner_email": "owner@example.com",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FOLLOWUP_PROJECT_NOT_ALLOWED"
    assert store.get_followup_draft(opportunity_id=uuid.UUID(opportunity_id), user_id=USER_A) is None


def test_allowed_project_succeeds(allow_project) -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    store = get_memory_store()
    transcript_id = _seed_transcript(store, uuid.UUID(opportunity_id), USER_A)
    with patch(
        "app.services.followup_pipeline.extract_followup",
        side_effect=lambda *a, **k: _fixture_complete("", "", {}),
    ):
        response = client.post(
            f"/opportunities/{opportunity_id}/followup/generate",
            headers=_headers(),
            json={
                "transcript_id": str(transcript_id),
                "project_key": FIXTURE_PROJECT,
                "project_statics": _statics(),
                "meeting_owner_email": "owner@example.com",
            },
        )
    assert response.status_code == 202
    draft = store.get_followup_draft(opportunity_id=uuid.UUID(opportunity_id), user_id=USER_A)
    assert draft is not None


def test_draft_persisted_fields(allow_project) -> None:
    store = get_memory_store()
    store.create_opportunity(
        user_id=USER_A,
        client_name="Acme",
        opportunity_name="Invoice",
        department="Finance",
        language="en",
    )
    opp = next(iter(store.opportunities.values()))
    _run_pipeline(store, opportunity_id=opp["id"])
    draft = store.get_followup_draft(opportunity_id=opp["id"], user_id=USER_A)
    assert draft
    for field in ("subject", "body", "review_flags", "status", "job_id", "extraction_json"):
        assert field in draft


def test_sent_log_has_no_transcript(allow_project) -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    store = get_memory_store()
    transcript_id = _seed_transcript(store, uuid.UUID(opportunity_id), USER_A)
    with patch(
        "app.services.followup_pipeline.extract_followup",
        side_effect=lambda *a, **k: _fixture_complete("", "", {}),
    ):
        client.post(
            f"/opportunities/{opportunity_id}/followup/generate",
            headers=_headers(),
            json={
                "transcript_id": str(transcript_id),
                "project_key": FIXTURE_PROJECT,
                "project_statics": _statics(),
                "meeting_owner_email": "owner@example.com",
            },
        )
    client.post(
        f"/opportunities/{opportunity_id}/followup/review/confirm",
        headers=_headers(),
    )
    record = client.post(
        f"/opportunities/{opportunity_id}/followup/delivery/record",
        headers=_headers(),
        json={"delivery_status": "sent_unknown", "final_subject": "Final", "final_body": "Final body"},
    )
    assert record.status_code == 200
    payload = str(record.json())
    assert "Lena Hoffmann (BOREK)" not in payload
    assert "transcript" not in payload.lower()


def test_sent_unknown_supported(allow_project) -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    store = get_memory_store()
    transcript_id = _seed_transcript(store, uuid.UUID(opportunity_id), USER_A)
    with patch(
        "app.services.followup_pipeline.extract_followup",
        side_effect=lambda *a, **k: _fixture_complete("", "", {}),
    ):
        client.post(
            f"/opportunities/{opportunity_id}/followup/generate",
            headers=_headers(),
            json={
                "transcript_id": str(transcript_id),
                "project_key": FIXTURE_PROJECT,
                "project_statics": _statics(),
                "meeting_owner_email": "owner@example.com",
            },
        )
    client.post(
        f"/opportunities/{opportunity_id}/followup/review/confirm",
        headers=_headers(),
    )
    record = client.post(
        f"/opportunities/{opportunity_id}/followup/delivery/record",
        headers=_headers(),
        json={"delivery_status": "sent_unknown"},
    )
    assert record.status_code == 200
    assert record.json()["delivery_status"] == "sent_unknown"


def test_egress_unlisted_field_blocked(allow_project) -> None:
    from app.services.followup_egress import enforce_followup_extraction_egress

    with pytest.raises(EgressBlockedError):
        enforce_followup_extraction_egress(
            {"transcript": "hello", "secret_field": "blocked"},
            opportunity_id=str(uuid.uuid4()),
        )


def test_restricted_egress_blocked(allow_project) -> None:
    from app.services.followup_egress import enforce_followup_extraction_egress

    with pytest.raises(EgressBlockedError):
        enforce_followup_extraction_egress(
            {"transcript": "hello", "restricted_marker": "no leave"},
            opportunity_id=str(uuid.uuid4()),
        )


def test_egress_audit_metadata_only(allow_project) -> None:
    from app.services.followup_egress import enforce_followup_extraction_egress

    store = get_memory_store()
    enforce_followup_extraction_egress(
        {"transcript": "CONFIDENTIAL TRANSCRIPT BODY", "calendar_meeting_date": "11.09.2026"},
        opportunity_id=str(uuid.uuid4()),
        store=store,
    )
    audits = list_egress_decisions()
    assert audits
    serialized = str(audits)
    assert "CONFIDENTIAL TRANSCRIPT BODY" not in serialized


def test_rls_user_isolation(allow_project) -> None:
    store = get_memory_store()
    store.create_opportunity(
        user_id=USER_A,
        client_name="Acme",
        opportunity_name="Invoice",
        department="Finance",
        language="en",
    )
    opp_a = next(row for row in store.opportunities.values() if row["created_by"] == USER_A)
    _run_pipeline(store, opportunity_id=opp_a["id"])
    drafts_b = store.list_followup_drafts_for_user(user_id=USER_B)
    assert drafts_b == []
    drafts_a = store.list_followup_drafts_for_user(user_id=USER_A)
    assert len(drafts_a) == 1
