"""AT-52: audit log infra on state-changing endpoints."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.services.audit.audit_log import AuditAction
from app.services.data.memory_store import get_memory_store
from tests.unit.api.test_at58_client_information_logo import PNG

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
ROUTERS_DIR = Path(__file__).resolve().parents[3] / "apps" / "services" / "api" / "app" / "routers"

CANONICAL_AUDIT_ACTIONS = frozenset(action.value for action in AuditAction)

STATE_CHANGING_ROUTER_FILES = (
    "opportunities.py",
    "transcripts.py",
    "frameworks.py",
    "presentations.py",
)


def _client() -> TestClient:
    return TestClient(create_app())


def _headers(user_id: uuid.UUID = USER_ID) -> dict[str, str]:
    token = create_test_access_token(
        user_id=user_id,
        email="owner@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def _audit_actions() -> list[str]:
    return [entry["action"] for entry in get_memory_store().list_audit_logs(actor_id=USER_ID)]


def _latest_audit() -> dict:
    entries = get_memory_store().list_audit_logs(actor_id=USER_ID)
    assert entries, "expected at least one audit entry"
    return entries[-1]


def test_record_audit_event_persists_actor_action_and_timestamp() -> None:
    client = _client()
    response = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Audit Corp",
            "opportunity_name": "Audit Trail",
            "department": "Ops",
            "language": "en",
        },
    )
    assert response.status_code == 201
    opportunity_id = uuid.UUID(response.json()["id"])

    entry = _latest_audit()
    assert entry["actor_id"] == USER_ID
    assert entry["action"] == AuditAction.OPPORTUNITY_CREATE.value
    assert entry["object_type"] == "opportunity"
    assert entry["object_id"] == opportunity_id
    assert entry["timestamp"] is not None


def test_state_changing_endpoints_emit_required_audit_actions() -> None:
    client = _client()

    opportunity = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Acme Corp",
            "opportunity_name": "Invoice Automation",
            "department": "Finance",
            "language": "en",
        },
    )
    assert opportunity.status_code == 201
    opportunity_id = opportunity.json()["id"]

    patch = client.patch(
        f"/opportunities/{opportunity_id}",
        headers=_headers(),
        json={"opportunity_name": "Updated"},
    )
    assert patch.status_code == 200

    transcript = client.post(
        f"/opportunities/{opportunity_id}/transcripts",
        headers=_headers(),
        files={"file": ("call.txt", b"Speaker 1: hello", "text/plain")},
    )
    assert transcript.status_code == 201
    transcript_id = transcript.json()["transcript"]["id"]

    regenerate_transcript = client.post(
        f"/opportunities/{opportunity_id}/transcripts/{transcript_id}/regenerate",
        headers=_headers(),
    )
    assert regenerate_transcript.status_code == 200

    generate_framework = client.post(
        f"/opportunities/{opportunity_id}/framework/generate",
        headers=_headers(),
    )
    assert generate_framework.status_code == 202
    framework_version_id = generate_framework.json()["framework_version_id"]

    regenerate_chapter = client.post(
        f"/opportunities/{opportunity_id}/framework/regenerate-chapter",
        headers=_headers(),
        json={"chapter_id": "3"},
    )
    assert regenerate_chapter.status_code == 202

    latest_framework = client.get(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
    )
    framework_json = latest_framework.json()["framework_json"]
    framework_json["title"] = "Edited title"
    update_framework = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert update_framework.status_code == 200

    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={"framework_version_id": framework_version_id},
    )
    assert confirm.status_code == 200

    render = client.post(
        f"/opportunities/{opportunity_id}/framework/render",
        headers=_headers(),
    )
    assert render.status_code == 202

    plan = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={"framework_version_id": framework_version_id},
    )
    assert plan.status_code == 202

    presentation = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={"framework_version_id": framework_version_id},
    )
    assert presentation.status_code == 202
    presentation_id = presentation.json()["presentation_id"]

    slides = client.get(f"/presentations/{presentation_id}/slides", headers=_headers())
    assert slides.status_code == 200
    slide_id = slides.json()[0]["id"]

    regenerate_slide = client.post(
        f"/presentations/{presentation_id}/slides/{slide_id}/regenerate",
        headers=_headers(),
    )
    assert regenerate_slide.status_code == 202

    latest_slides = client.get(
        f"/presentations/{presentation_id}/slides",
        headers=_headers(),
    )
    slide_id = latest_slides.json()[0]["id"]
    current_layout = latest_slides.json()[0]["layout_id"]

    change_layout = client.post(
        f"/presentations/{presentation_id}/slides/{slide_id}/change-layout",
        headers=_headers(),
        json={"layout_id": current_layout},
    )
    assert change_layout.status_code == 202

    delete_transcript = client.delete(
        f"/opportunities/{opportunity_id}/transcripts/{transcript_id}",
        headers=_headers(),
    )
    assert delete_transcript.status_code == 204

    logo_path = f"/opportunities/{opportunity_id}/client-logo"
    upload_logo = client.put(
        logo_path,
        headers=_headers(),
        files={"file": ("client.png", PNG, "image/png")},
    )
    assert upload_logo.status_code == 200
    replace_logo = client.put(
        logo_path,
        headers=_headers(),
        files={"file": ("client.png", PNG, "image/png")},
    )
    assert replace_logo.status_code == 200
    delete_logo = client.delete(logo_path, headers=_headers())
    assert delete_logo.status_code == 204

    recorded = set(_audit_actions())
    assert CANONICAL_AUDIT_ACTIONS.issubset(recorded)


def test_backlog_highlighted_actions_are_covered() -> None:
    required = {
        AuditAction.FRAMEWORK_CONFIRM.value,
        AuditAction.FRAMEWORK_REGENERATE_CHAPTER.value,
        AuditAction.FRAMEWORK_RENDER.value,
        AuditAction.SLIDE_CHANGE_LAYOUT.value,
        AuditAction.SLIDE_REGENERATE.value,
        AuditAction.TRANSCRIPT_REGENERATE.value,
    }
    assert required.issubset(CANONICAL_AUDIT_ACTIONS)


def test_state_changing_routers_import_and_call_record_audit_event() -> None:
    for filename in STATE_CHANGING_ROUTER_FILES:
        source = (ROUTERS_DIR / filename).read_text(encoding="utf-8")
        assert "record_audit_event" in source, f"{filename} must call record_audit_event"

    combined = "\n".join(
        (ROUTERS_DIR / filename).read_text(encoding="utf-8")
        for filename in STATE_CHANGING_ROUTER_FILES
    )
    handler_count = len(
        re.findall(r"@(?:router|opportunity_router|plan_router)\.(post|patch|delete)\(", combined)
    )
    audit_call_count = combined.count("record_audit_event(")
    assert audit_call_count >= handler_count, (
        "every POST/PATCH/DELETE handler must emit an audit entry; handlers with "
        "multiple audited outcomes may contain more than one call"
    )


def test_audit_log_module_exists_at_expected_path() -> None:
    audit_module = (
        Path(__file__).resolve().parents[3]
        / "apps"
        / "services"
        / "api"
        / "app"
        / "services"
        / "audit"
        / "audit_log.py"
    )
    assert audit_module.is_file()
    source = audit_module.read_text(encoding="utf-8")
    assert "def record_audit_event" in source
    assert "actor_id" in source
    assert "action" in source
    assert "timestamp" in source or "append_audit_log" in source
