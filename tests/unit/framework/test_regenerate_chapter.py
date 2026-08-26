"""ES-12 — single-chapter regenerate leaves other chapters byte-equal."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.framework.pipeline import generate_customer_framework
from services.framework.regenerate_chapter import ChapterRegenError, regenerate_chapter

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures"


def _framework() -> dict:
    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    overrides = json.loads((FIXTURES / "engine_overrides.invoice_3way.json").read_text(encoding="utf-8"))
    return generate_customer_framework(
        [model],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )


def test_unrelated_chapters_byte_equal_except_changelog() -> None:
    original = _framework()
    snapshot = copy.deepcopy(original)
    replacement = copy.deepcopy(original["chapters"][1])
    replacement["body"] = list(replacement["body"]) + [
        {"block": "prose", "text": "Sponsor recap refreshed from the same sources."}
    ]
    updated = regenerate_chapter(
        original,
        "1",
        replacement,
        reason="sponsor wording",
        now=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
    )

    assert original == snapshot
    assert updated["version"] == original["version"] + 1
    assert updated["change_log"][-1] == "Chapter 1 regenerated: sponsor wording"
    assert updated["chapters"][1]["body"] != original["chapters"][1]["body"]
    for index, chapter in enumerate(original["chapters"]):
        if index == 1:
            continue
        assert updated["chapters"][index] == chapter
    assert original["change_log"] == snapshot["change_log"]


def test_missing_source_refs_are_rejected() -> None:
    original = _framework()
    replacement = copy.deepcopy(original["chapters"][2])
    replacement["source_refs"] = []
    with pytest.raises(ChapterRegenError) as exc_info:
        regenerate_chapter(original, "2", replacement, reason="drop citations")
    assert "source_refs" in exc_info.value.user_message


def test_confirmed_report_cannot_be_regenerated() -> None:
    original = _framework()
    original["status"] = "confirmed"
    replacement = copy.deepcopy(original["chapters"][0])
    with pytest.raises(ChapterRegenError):
        regenerate_chapter(original, "0", replacement, reason="after confirm")
