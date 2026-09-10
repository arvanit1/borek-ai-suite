"""BT-31: journey-stage eligibility, lineage, and JJ-31 prior-stage context."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import jsonschema
import pytest
from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.schemas.jobs import JobStage
from app.services import job_service
from app.services.data.memory_store import get_memory_store
from app.services.journey_stage import (
    build_prior_stage_context,
    evaluate_opportunity_eligibility,
    load_prior_stage_context_for_version,
    resolve_prior_framework,
)
from services.gamma.payload import build_gamma_content_payload

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
ROOT = Path(__file__).resolve().parents[3]
ELIGIBILITY_SCHEMA = json.loads(
    (ROOT / "packages" / "contracts" / "journey_stage_eligibility.schema.json").read_text(
        encoding="utf-8"
    )
)
ELIGIBILITY_FIXTURE = json.loads(
    (
        ROOT
        / "packages"
        / "contracts"
        / "fixtures"
        / "journey_stage_eligibility"
        / "first_contact_only.json"
    ).read_text(encoding="utf-8")
)


def _client() -> TestClient:
    return TestClient(create_app())


def _headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=USER_ID,
        email="owner@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def _create_opportunity(client: TestClient, *, name: str = "Invoice Automation") -> str:
    response = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Acme Corp",
            "opportunity_name": name,
            "department": "Finance",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _confirm_framework(client: TestClient, opportunity_id: str) -> str:
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200, confirm.text
    return confirm.json()["id"]


def _generate_stage(
    client: TestClient,
    opportunity_id: str,
    journey_stage: str,
) -> dict:
    _confirm_framework(client, opportunity_id)
    plan = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={"journey_stage": journey_stage},
    )
    assert plan.status_code == 202, plan.text
    generated = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={
            "presentation_plan_id": plan.json()["presentation_plan_id"],
            "journey_stage": journey_stage,
        },
    )
    assert generated.status_code == 202, generated.text
    return generated.json()


def _eligibility(
    client: TestClient,
    opportunity_id: str,
    journey_stage: str | None = None,
) -> dict:
    query = f"?journey_stage={journey_stage}" if journey_stage else ""
    response = client.get(
        f"/opportunities/{opportunity_id}/journey-stage-eligibility{query}",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _latest_version(presentation_id: str) -> dict:
    return get_memory_store().get_latest_presentation_version(
        presentation_id=uuid.UUID(presentation_id),
        user_id=USER_ID,
    )


def _stage_map(payload: dict) -> dict[str, dict]:
    return {row["journey_stage"]: row for row in payload["stages"]}


def test_eligibility_contract_is_deterministic_and_matches_schema() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    payload = _eligibility(client, opportunity_id)
    jsonschema.validate(instance=payload, schema=ELIGIBILITY_SCHEMA)
    jsonschema.validate(instance=ELIGIBILITY_FIXTURE, schema=ELIGIBILITY_SCHEMA)

    stages = _stage_map(payload)
    assert payload["schema_version"] == "1.0"
    assert payload["requested_journey_stage"] is None
    assert payload["startable"] is True
    assert stages["first_contact"]["startable"] is True
    assert stages["first_contact"]["prior_stage_presentation_version_id"] is None
    assert stages["deepening"] == {
        "journey_stage": "deepening",
        "startable": False,
        "prerequisite_stage": "first_contact",
        "prior_stage_presentation_version_id": None,
        "reason": "NO_COMPLETED_PREREQUISITE",
        "next_action": "complete_first_contact",
    }
    assert stages["concretisation"]["next_action"] == "complete_deepening"


def test_first_contact_is_eligible_and_persists_null_prior() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    requested = _eligibility(client, opportunity_id, "first_contact")
    assert requested["requested_journey_stage"] == "first_contact"
    assert requested["startable"] is True
    assert requested["prior_stage_presentation_version_id"] is None

    generated = _generate_stage(client, opportunity_id, "first_contact")
    version = _latest_version(generated["presentation_id"])
    assert version["journey_stage"] == "first_contact"
    assert version["prior_stage_presentation_version_id"] is None


def test_omitted_stage_starts_first_contact_not_deepening() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    _confirm_framework(client, opportunity_id)
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
    version = _latest_version(generated.json()["presentation_id"])
    assert version["journey_stage"] == "first_contact"
    assert version["prior_stage_presentation_version_id"] is None


def test_deepening_locked_refuses_before_job_or_plan() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    _confirm_framework(client, opportunity_id)
    store = get_memory_store()
    jobs_before = len(store.generation_jobs)
    plans_before = len(store.presentation_plans)
    presentations_before = len(store.presentations)

    blocked = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={"journey_stage": "deepening"},
    )
    assert blocked.status_code == 400
    assert blocked.status_code != 500
    error = blocked.json()["error"]
    assert error["code"] == "INPUT_REQUIRED"
    assert error["detail"]["next_action"] == "complete_first_contact"
    assert error["detail"]["requested_journey_stage"] == "deepening"
    assert error["detail"]["reason"] == "NO_COMPLETED_PREREQUISITE"
    assert len(store.generation_jobs) == jobs_before
    assert len(store.presentation_plans) == plans_before
    assert len(store.presentations) == presentations_before


def test_deepening_eligible_persists_lineage_and_supplies_jj31_context() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    first = _generate_stage(client, opportunity_id, "first_contact")
    first_version = _latest_version(first["presentation_id"])
    eligibility = _eligibility(client, opportunity_id, "deepening")
    assert eligibility["startable"] is True
    assert eligibility["prior_stage_presentation_version_id"] == str(first_version["id"])

    deepening = _generate_stage(client, opportunity_id, "deepening")
    later = _latest_version(deepening["presentation_id"])
    assert later["journey_stage"] == "deepening"
    assert later["prior_stage_presentation_version_id"] == first_version["id"]

    store = get_memory_store()
    opportunity = store.get_opportunity(
        opportunity_id=uuid.UUID(opportunity_id),
        user_id=USER_ID,
    )
    prior_framework = resolve_prior_framework(
        store,
        prior_version=first_version,
        user_id=USER_ID,
    )
    assert prior_framework["status"] == "confirmed"
    context = build_prior_stage_context(
        store,
        opportunity=opportunity,
        prior_version=first_version,
        user_id=USER_ID,
    )
    assert context["slots"]
    payload = build_gamma_content_payload(
        opportunity=opportunity,
        framework={
            "status": "confirmed",
            "chapters": [
                {
                    "chapter_id": "13",
                    "title": "Next steps",
                    "body": "Confirm the pilot scope.",
                }
            ],
        },
        stage="deepening",
        prior_stage_context=context,
    )
    blob = " ".join(slot["value"] for slot in payload["slots"])
    assert any(slot["value"] for slot in context["slots"] if slot["value"] and slot["value"] in blob)
    assert payload["stage"] == "deepening"
    assert all(item["kind"] != "pricing" for item in payload["grounded_facts"])


def test_concretisation_locked_without_completed_deepening() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    _generate_stage(client, opportunity_id, "first_contact")
    store = get_memory_store()
    jobs_before = len(store.generation_jobs)

    blocked = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={"journey_stage": "concretisation"},
    )
    assert blocked.status_code == 400
    error = blocked.json()["error"]
    assert error["code"] == "INPUT_REQUIRED"
    assert error["detail"]["next_action"] == "complete_deepening"
    assert error["detail"]["reason"] == "NO_COMPLETED_PREREQUISITE"
    assert len(store.generation_jobs) == jobs_before


def test_concretisation_eligible_uses_deepening_lineage() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    _generate_stage(client, opportunity_id, "first_contact")
    deepening = _generate_stage(client, opportunity_id, "deepening")
    deepening_version = _latest_version(deepening["presentation_id"])

    generated = _generate_stage(client, opportunity_id, "concretisation")
    version = _latest_version(generated["presentation_id"])
    assert version["journey_stage"] == "concretisation"
    assert version["prior_stage_presentation_version_id"] == deepening_version["id"]

    store = get_memory_store()
    opportunity = store.get_opportunity(
        opportunity_id=uuid.UUID(opportunity_id),
        user_id=USER_ID,
    )
    framework = resolve_prior_framework(
        store,
        prior_version=deepening_version,
        user_id=USER_ID,
    )
    context = build_prior_stage_context(
        store,
        opportunity=opportunity,
        prior_version=deepening_version,
        user_id=USER_ID,
    )
    assert framework["id"]
    assert context["slots"]
    prior = store.get_presentation_version(
        presentation_version_id=version["prior_stage_presentation_version_id"],
        user_id=USER_ID,
    )
    assert prior["journey_stage"] == "deepening"


def test_incomplete_and_foreign_prior_do_not_unlock() -> None:
    client = _client()
    first_opp = _create_opportunity(client, name="Own deal")
    other_opp = _create_opportunity(client, name="Other deal")
    _generate_stage(client, other_opp, "first_contact")
    _confirm_framework(client, first_opp)

    foreign = _eligibility(client, first_opp, "deepening")
    assert foreign["startable"] is False
    assert foreign["next_action"] == "complete_first_contact"

    first = _generate_stage(client, first_opp, "first_contact")
    version = _latest_version(first["presentation_id"])
    version["status"] = "generating"
    incomplete = _eligibility(client, first_opp, "deepening")
    assert incomplete["startable"] is False
    assert incomplete["reason"] == "PREREQUISITE_INCOMPLETE"
    assert incomplete["next_action"] == "complete_first_contact"


def test_broken_prior_framework_is_input_required_not_500() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    first = _generate_stage(client, opportunity_id, "first_contact")
    store = get_memory_store()
    first_version = _latest_version(first["presentation_id"])
    presentation = store.get_presentation(
        presentation_id=first_version["presentation_id"],
        user_id=USER_ID,
    )
    plan = store.get_presentation_plan(
        presentation_plan_id=presentation["presentation_plan_id"],
        user_id=USER_ID,
    )
    store.framework_versions[plan["framework_version_id"]]["status"] = "draft"

    payload = evaluate_opportunity_eligibility(
        store,
        opportunity_id=uuid.UUID(opportunity_id),
        user_id=USER_ID,
        requested_journey_stage="deepening",
    )
    assert payload["startable"] is False
    assert payload["reason"] == "PRIOR_FRAMEWORK_UNAVAILABLE"
    assert payload["next_action"] == "regenerate_prior_stage"

    blocked = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={"journey_stage": "deepening"},
    )
    assert blocked.status_code == 400
    assert blocked.status_code != 500
    assert blocked.json()["error"]["code"] == "INPUT_REQUIRED"
    assert blocked.json()["error"]["detail"]["next_action"] == "regenerate_prior_stage"


def test_missing_prior_version_is_superseded_input_required() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    first = _generate_stage(client, opportunity_id, "first_contact")
    store = get_memory_store()
    first_version = _latest_version(first["presentation_id"])
    missing_id = uuid.uuid4()
    ghost = {
        "journey_stage": "deepening",
        "prior_stage_presentation_version_id": missing_id,
        "status": "generating",
    }
    with pytest.raises(Exception) as raised:
        load_prior_stage_context_for_version(
            store,
            opportunity=store.get_opportunity(
                opportunity_id=uuid.UUID(opportunity_id),
                user_id=USER_ID,
            ),
            version=ghost,
            user_id=USER_ID,
        )
    assert raised.value.status_code == 400
    assert raised.value.detail["code"] == "INPUT_REQUIRED"
    assert raised.value.detail["detail"]["reason"] == "PREREQUISITE_SUPERSEDED"
    assert first_version["id"]


def test_eligibility_is_independent_of_presentation_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    payloads = []
    for engine in ("internal", "gamma"):
        monkeypatch.setattr(settings, "PRESENTATION_ENGINE", engine)
        payloads.append(_eligibility(client, opportunity_id, "deepening"))
    assert payloads[0] == payloads[1]
    assert payloads[0]["startable"] is False
    assert payloads[0]["next_action"] == "complete_first_contact"

    _generate_stage(client, opportunity_id, "first_contact")
    unlocked = []
    for engine in ("internal", "gamma"):
        monkeypatch.setattr(settings, "PRESENTATION_ENGINE", engine)
        unlocked.append(_eligibility(client, opportunity_id, "deepening"))
    assert unlocked[0]["startable"] is True
    assert unlocked[0]["prior_stage_presentation_version_id"] == unlocked[1][
        "prior_stage_presentation_version_id"
    ]


def test_at56_reconnect_does_not_duplicate_jobs() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    _confirm_framework(client, opportunity_id)
    plan_id = uuid.uuid4()
    job = job_service.create_job(
        uuid.UUID(opportunity_id),
        "presentation_planning",
        enqueue={"presentation_plan_id": str(plan_id), "user_id": str(USER_ID)},
        repository=get_memory_store(),
    )
    job_service.advance_stage(
        job.id,
        JobStage.TRANSCRIPT_PROCESSING,
        repository=get_memory_store(),
    )
    with patch("app.worker.run_presentation_planning_task") as mocked:
        first = client.post(
            f"/opportunities/{opportunity_id}/presentation-plan/generate",
            headers=_headers(),
            json={"journey_stage": "first_contact"},
        )
        second = client.post(
            f"/opportunities/{opportunity_id}/presentation-plan/generate",
            headers=_headers(),
            json={"journey_stage": "first_contact"},
        )
    assert first.json()["job_id"] == str(job.id) == second.json()["job_id"]
    assert first.json()["is_existing_job"] is True
    assert second.json()["is_existing_job"] is True
    mocked.run.assert_not_called()
    planning_jobs = [
        row
        for row in get_memory_store().generation_jobs.values()
        if str(row.get("job_type") or "") == "presentation_planning"
    ]
    assert len(planning_jobs) == 1


def test_lineage_is_queryable_after_generation() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    first = _generate_stage(client, opportunity_id, "first_contact")
    deepening = _generate_stage(client, opportunity_id, "deepening")
    store = get_memory_store()
    later = _latest_version(deepening["presentation_id"])
    prior = store.get_presentation_version(
        presentation_version_id=later["prior_stage_presentation_version_id"],
        user_id=USER_ID,
    )
    assert later["journey_stage"] == "deepening"
    assert prior["journey_stage"] == "first_contact"
    assert prior["id"] == _latest_version(first["presentation_id"])["id"]
    framework = resolve_prior_framework(store, prior_version=prior, user_id=USER_ID)
    presentation = store.get_presentation(
        presentation_id=prior["presentation_id"],
        user_id=USER_ID,
    )
    plan = store.get_presentation_plan(
        presentation_plan_id=presentation["presentation_plan_id"],
        user_id=USER_ID,
    )
    assert framework["id"] == plan["framework_version_id"]


def test_unknown_stage_is_classified() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    _confirm_framework(client, opportunity_id)
    blocked = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={"journey_stage": "offer_grade"},
    )
    assert blocked.status_code == 400
    error = blocked.json()["error"]
    assert error["code"] == "JOURNEY_STAGE_UNKNOWN"
    assert error["detail"]["next_action"] == "select_journey_stage"
