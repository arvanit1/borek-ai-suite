"""AT-41: framework endpoint unit tests."""

from __future__ import annotations

import copy
import uuid
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.services import framework_generation
from app.services.data.memory_store import get_memory_store
from app.services.framework_versioning import framework_source_revision
from app.services.stage_a_orchestration import _redact_framework_for_llm

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _client() -> TestClient:
    return TestClient(create_app())


def _headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=USER_ID,
        email="owner@example.com",
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


def _without_lifecycle(framework_json: dict) -> dict:
    cleaned = copy.deepcopy(framework_json)
    fields = {
        "version",
        "previous_version_id",
        "status",
        "created_at",
        "updated_at",
        "change_log",
        "confirmed_by",
        "confirmed_at",
    }
    for field in fields:
        cleaned.pop(field, None)
    if isinstance(cleaned.get("customer_view"), dict):
        for field in fields:
            cleaned["customer_view"].pop(field, None)
    return cleaned


def test_generate_get_and_confirm_framework() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)

    generate = client.post(
        f"/opportunities/{opportunity_id}/framework/generate",
        headers=_headers(),
    )
    assert generate.status_code == 202
    body = generate.json()
    assert body["status"] == "queued"
    assert body["framework_version_id"]
    assert body["job_id"]

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    assert latest.status_code == 200
    draft_row = latest.json()
    framework_version_id = draft_row["id"]
    draft_json = copy.deepcopy(draft_row["framework_json"])
    assert latest.json()["status"] == "draft"

    by_id = client.get(f"/frameworks/{framework_version_id}", headers=_headers())
    assert by_id.status_code == 200

    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"
    confirmed = confirm.json()
    assert confirmed["id"] != framework_version_id
    assert confirmed["version_number"] == draft_row["version_number"] + 1
    assert confirmed["framework_json"]["version"] == confirmed["version_number"]
    assert confirmed["framework_json"]["previous_version_id"] == framework_version_id
    assert confirmed["framework_json"]["chapters"] == draft_json["chapters"]
    assert _without_lifecycle(confirmed["framework_json"]) == _without_lifecycle(draft_json)

    unchanged_draft = client.get(f"/frameworks/{framework_version_id}", headers=_headers()).json()
    assert unchanged_draft["status"] == "draft"
    assert unchanged_draft["framework_json"] == draft_json


def _set_latest_framework_status(opportunity_id: str, status: str) -> None:
    store = get_memory_store()
    for row in store.framework_versions.values():
        if str(row["opportunity_id"]) == opportunity_id:
            row["status"] = status
            row["framework_json"]["status"] = status


def test_regenerate_chapter_enqueues_job() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    before_row = client.get(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
    ).json()
    before = copy.deepcopy(before_row["framework_json"])

    response = client.post(
        f"/opportunities/{opportunity_id}/framework/regenerate-chapter",
        headers=_headers(),
        json={"chapter_id": "3"},
    )
    assert response.status_code == 202
    assert response.json()["job_id"]
    job = client.get(f"/jobs/{response.json()['job_id']}", headers=_headers())
    assert job.status_code == 200
    assert job.json()["status"] == "COMPLETED"
    assert job.json()["result"]["source_framework_version_id"] == before_row["id"]

    after_row = client.get(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
    ).json()
    after = after_row["framework_json"]
    assert after_row["id"] != before_row["id"]
    assert after_row["version_number"] == before_row["version_number"] + 1
    assert after["version"] == before["version"] + 1
    assert after["previous_version_id"] == before_row["id"]
    for index, chapter in enumerate(before["chapters"]):
        if chapter["chapter_id"] == "3":
            assert after["chapters"][index] != chapter
        else:
            assert after["chapters"][index] == chapter

    source = client.get(f"/frameworks/{before_row['id']}", headers=_headers())
    assert source.json()["framework_json"] == before


def test_completed_regeneration_retry_reuses_reserved_version(monkeypatch) -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    source = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers()).json()
    response = client.post(
        f"/opportunities/{opportunity_id}/framework/regenerate-chapter",
        headers=_headers(),
        json={"chapter_id": "3"},
    )
    job = client.get(f"/jobs/{response.json()['job_id']}", headers=_headers()).json()
    destination_id = job["result"]["framework_version_id"]

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("chapter generation repeated")

    monkeypatch.setattr(
        framework_generation,
        "regenerate_framework_chapter_from_transcripts",
        fail_if_called,
    )

    reused = framework_generation.execute_framework_regenerate_chapter(
        get_memory_store(),
        opportunity_id=UUID(opportunity_id),
        user_id=USER_ID,
        source_framework_version_id=UUID(source["id"]),
        framework_version_id=UUID(destination_id),
        chapter_id="3",
        source_revision=framework_source_revision(
            get_memory_store().get_framework_version(
                framework_version_id=UUID(source["id"]),
                user_id=USER_ID,
            )
        ),
    )

    assert str(reused["id"]) == destination_id
    assert len(get_memory_store().framework_versions) == 2


def test_completed_framework_generation_retry_reuses_reserved_version(monkeypatch) -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    generated = client.post(
        f"/opportunities/{opportunity_id}/framework/generate",
        headers=_headers(),
    ).json()
    reserved_id = generated["framework_version_id"]

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("framework generation repeated")

    monkeypatch.setattr(
        framework_generation,
        "generate_framework_from_transcripts",
        fail_if_called,
    )
    reused = framework_generation.execute_framework_generate(
        get_memory_store(),
        opportunity_id=UUID(opportunity_id),
        user_id=USER_ID,
        framework_version_id=UUID(reserved_id),
    )

    assert str(reused["id"]) == reserved_id
    assert len(get_memory_store().framework_versions) == 1


def test_regeneration_rejects_source_edited_during_chapter_generation(monkeypatch) -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    store = get_memory_store()
    source = store.get_latest_framework(opportunity_id=UUID(opportunity_id), user_id=USER_ID)
    revision = framework_source_revision(source)

    def edit_source_during_generation(*_args, **_kwargs):
        replacement = copy.deepcopy(source["framework_json"]["chapters"][3])
        replacement["body"] = [{"block": "prose", "text": "Regenerated aim."}]
        source["framework_json"]["title"] = "Concurrent manual edit"
        return replacement

    monkeypatch.setattr(
        framework_generation,
        "regenerate_framework_chapter_from_transcripts",
        edit_source_during_generation,
    )

    with pytest.raises(HTTPException) as raised:
        framework_generation.execute_framework_regenerate_chapter(
            store,
            opportunity_id=UUID(opportunity_id),
            user_id=USER_ID,
            source_framework_version_id=source["id"],
            framework_version_id=uuid.uuid4(),
            chapter_id="3",
            source_revision=revision,
        )

    assert raised.value.status_code == 409
    assert raised.value.detail["code"] == "FRAMEWORK_VERSION_CONFLICT"
    assert len(store.framework_versions) == 1


def test_framework_context_is_redacted_before_chapter_llm() -> None:
    framework = {
        "title": "Contact Jane Doe at jane.doe@example.com or +49 151 12345678",
        "chapters": [
            {
                "body": "Jane Doe owns the approval.",
                "private@example.com": "Do not leak PII from keys either.",
            }
        ],
    }

    redacted = _redact_framework_for_llm(framework, enabled=True)

    serialized = str(redacted)
    assert "jane.doe@example.com" not in serialized
    assert "private@example.com" not in serialized
    assert "+49 151 12345678" not in serialized
    assert framework["title"].endswith("+49 151 12345678")


def test_update_framework_persists_edits() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    framework_json = latest.json()["framework_json"]
    framework_json["title"] = "Updated framework title"
    framework_json["chapters"][1]["body"] = [
        {"summary": "Edited management summary with traceable facts."}
    ]

    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 200
    assert patch.json()["framework_json"]["title"] == "Updated framework title"

    reloaded = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    assert reloaded.json()["framework_json"]["title"] == "Updated framework title"


def test_update_framework_rejects_invalid_contract_without_persisting() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    original = latest.json()["framework_json"]
    invalid = dict(original)
    invalid["chapters"] = []

    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": invalid},
    )

    assert patch.status_code == 422
    assert patch.json()["error"]["code"] == "FRAMEWORK_VALIDATION_FAILED"
    reloaded = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    assert reloaded.json()["framework_json"] == original


def test_update_framework_preserves_per_fact_evidence_after_reload() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    framework_json = latest.json()["framework_json"]
    fact_a = {
        "conversation_id": "C-FACT-A",
        "speaker_role": "operator",
        "excerpt_pointer": "turn-12",
    }
    fact_b = {
        "conversation_id": "C-FACT-B",
        "speaker_role": "it",
        "excerpt_pointer": "turn-34",
    }
    chapter = framework_json["chapters"][2]
    chapter["body"] = [
        {
            "block": "prose",
            "text": "Edited nested fact A",
            "source_refs": [fact_a],
            "provenance": "source_fact",
        },
        {
            "block": "table",
            "columns": ["KPI"],
            "rows": [["auto-match"]],
            "source_refs": [fact_b],
            "provenance": "user_input",
        },
    ]
    chapter["source_refs"] = [
        {
            "conversation_id": "C-CHAPTER",
            "speaker_role": "dept_head",
            "excerpt_pointer": "turn-1",
        }
    ]

    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 200, patch.text

    reloaded = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    assert reloaded.status_code == 200, reloaded.text
    saved = reloaded.json()["framework_json"]["chapters"][2]
    assert saved["body"][0]["text"] == "Edited nested fact A"
    assert saved["body"][0]["source_refs"] == [fact_a]
    assert saved["body"][1]["source_refs"] == [fact_b]
    assert saved["body"][0]["source_refs"] != saved["body"][1]["source_refs"]
    assert saved["source_refs"][0]["conversation_id"] == "C-CHAPTER"
    assert saved["body"][0]["source_refs"] != saved["source_refs"]


def test_review_actions_allow_in_review_and_lock_after_confirm() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    _set_latest_framework_status(opportunity_id, "in_review")

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    assert latest.json()["status"] == "in_review"
    framework_json = latest.json()["framework_json"]
    framework_json["title"] = "Reviewed in-review title"

    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 200
    assert patch.json()["framework_json"]["title"] == "Reviewed in-review title"

    regenerate = client.post(
        f"/opportunities/{opportunity_id}/framework/regenerate-chapter",
        headers=_headers(),
        json={"chapter_id": "3"},
    )
    assert regenerate.status_code == 202

    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    blocked_regenerate = client.post(
        f"/opportunities/{opportunity_id}/framework/regenerate-chapter",
        headers=_headers(),
        json={"chapter_id": "3"},
    )
    assert blocked_regenerate.status_code == 409
    assert blocked_regenerate.json()["error"]["code"] == "FRAMEWORK_IMMUTABLE"


def test_update_framework_rejects_confirmed_version() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    confirmed = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    framework_json = latest.json()["framework_json"]
    framework_json["title"] = "Should not save"

    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 409
    assert patch.json()["error"]["code"] == "FRAMEWORK_IMMUTABLE"


def test_reopen_for_correction_unlocks_confirmed_framework() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200
    confirmed = copy.deepcopy(confirm.json())

    reopened = client.post(
        f"/opportunities/{opportunity_id}/framework/reopen-for-correction",
        headers=_headers(),
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "in_review"
    assert reopened.json()["id"] != confirmed["id"]
    assert reopened.json()["version_number"] == confirmed["version_number"] + 1
    assert reopened.json()["framework_json"]["previous_version_id"] == confirmed["id"]
    assert reopened.json()["framework_json"]["version"] == reopened.json()["version_number"]
    assert "confirmed_by" not in reopened.json()["framework_json"]
    assert "confirmed_at" not in reopened.json()["framework_json"]
    assert _without_lifecycle(reopened.json()["framework_json"]) == _without_lifecycle(confirmed["framework_json"])
    preserved = client.get(f"/frameworks/{confirmed['id']}", headers=_headers()).json()
    assert preserved == confirmed

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    framework_json = latest.json()["framework_json"]
    framework_json["title"] = "Corrected title"
    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 200
    assert patch.json()["framework_json"]["title"] == "Corrected title"

    already_open = client.post(
        f"/opportunities/{opportunity_id}/framework/reopen-for-correction",
        headers=_headers(),
    )
    assert already_open.status_code == 400
    assert already_open.json()["error"]["code"] == "FRAMEWORK_NOT_CONFIRMED"


def test_render_requires_confirmed_framework() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    blocked = client.post(
        f"/opportunities/{opportunity_id}/framework/render",
        headers=_headers(),
    )
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "FRAMEWORK_NOT_CONFIRMED"

    confirmed = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    allowed = client.post(
        f"/opportunities/{opportunity_id}/framework/render",
        headers=_headers(),
    )
    assert allowed.status_code == 202
    assert allowed.json()["job_id"]

    pdf = client.get(
        f"/frameworks/{confirmed.json()['id']}/render?format=pdf",
        headers=_headers(),
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")


def test_confirm_framework_blocks_es13_chapter6_contradiction() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    framework_json = latest.json()["framework_json"]
    chapter_6 = next(ch for ch in framework_json["chapters"] if ch["chapter_id"] == "6")
    ai_split = next(block for block in chapter_6["body"] if block.get("block") == "ai_split")
    ai_split["used_for"] = ["Deciding whether a case matches"]
    ai_split["not_used_for"] = ["Deciding whether a case matches", "Evaluating employees"]

    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 200

    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 422
    assert confirm.json()["error"]["code"] == "PRE_CONFIRM_FAILED"
    assert "contradicts" in confirm.json()["error"]["message"].lower()

    reloaded = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    assert reloaded.json()["status"] == "draft"


def test_framework_review_returns_summary_and_attention_signals() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    review = client.get(f"/opportunities/{opportunity_id}/framework/review", headers=_headers())
    assert review.status_code == 200
    body = review.json()
    assert body["review_summary"]["headline"]
    assert isinstance(body["attention_signals"], list)
    assert body["review_state"]
    assert body["pii_handling"]["applied_before_llm"] is True
    assert "prompt_observability" in body


def test_framework_review_rebuilds_after_chapter_edit() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    framework_json = latest.json()["framework_json"]
    framework_json["review_summary"] = {
        **dict(framework_json.get("review_summary") or {}),
        "confirm_ready": True,
        "confirm_block_reason": None,
        "blocking_items": [],
    }
    framework_json["attention"] = {"review_state": "READY_TO_APPROVE", "signals": []}
    chapter_6 = next(ch for ch in framework_json["chapters"] if ch["chapter_id"] == "6")
    ai_split = next(block for block in chapter_6["body"] if block.get("block") == "ai_split")
    ai_split["used_for"] = ["Deciding whether a case matches"]
    ai_split["not_used_for"] = ["Deciding whether a case matches", "Evaluating employees"]

    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 200

    review = client.get(f"/opportunities/{opportunity_id}/framework/review", headers=_headers())
    assert review.status_code == 200
    assert review.json()["review_state"] == "BLOCKING_CONTRADICTION"
    assert review.json()["review_summary"]["confirm_ready"] is False
