"""BT-33 / MS-32 FollowupDraft schema contract."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from services.followup.extraction import load_followup_fixture
from services.followup.rendering import load_followup_draft_schema, render_followup_draft

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "followup_draft.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_draft_schema_matches_renderer_output(schema: dict) -> None:
    _, extraction, _ = load_followup_fixture("workshop_clear")
    statics = {
        "project_name": "Acme Invoice Automation",
        "salutation_style": "informal",
        "recipient_first_name": "Markus",
        "time_reference": "today",
        "sender_name": "Lena Hoffmann",
        "sender_role": "Delivery Lead",
    }
    draft = render_followup_draft(extraction, statics)
    jsonschema.validate(instance=draft, schema=schema)
    assert draft["status"] == "draft"


def test_draft_schema_rejects_missing_status(schema: dict) -> None:
    payload = {
        "subject": "Subject",
        "body": "Body",
        "review_flags": [],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)
