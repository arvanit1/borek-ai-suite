"""Stage 3 black-box eval: KM → Framework without a golden FrameworkObject input."""

from __future__ import annotations

import json
from pathlib import Path

from packages.contracts.schema_consumer import validate_framework_object
from services.framework.chapter_validators import validate_all_chapters
from services.framework.chapter_validators.base import ChapterValidationError
from services.framework.pipeline import generate_customer_framework

ROOT = Path(__file__).resolve().parents[3]
KM_PATH = ROOT / "packages" / "contracts" / "fixtures" / "knowledge_model.invoice_3way.json"
REGISTRY = json.loads((ROOT / "packages" / "contracts" / "chapter_registry.json").read_text(encoding="utf-8"))


def _knowledge_model() -> dict:
    return json.loads(KM_PATH.read_text(encoding="utf-8"))


def _generate() -> dict:
    return generate_customer_framework(
        [_knowledge_model()],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
    )


def test_blackbox_eval_starts_from_knowledge_model_not_a_framework_fixture() -> None:
    model = _knowledge_model()
    assert "chapters" not in model
    assert "facts" in model
    framework = _generate()
    assert framework["chapters"]
    assert framework is not model


def test_blackbox_eval_emits_fourteen_valid_chapters() -> None:
    framework = _generate()
    validate_framework_object(framework)
    expected = [(item["chapter_id"], item["title"]) for item in REGISTRY["chapters"]]
    actual = [(str(chapter["chapter_id"]), chapter["title"]) for chapter in framework["chapters"]]
    assert actual == expected
    try:
        issues = validate_all_chapters(framework)
    except ChapterValidationError as exc:
        raise AssertionError(exc.user_message) from exc
    assert issues == []


def test_blackbox_eval_keeps_typed_chapter_kinds() -> None:
    framework = _generate()
    by_id = {str(chapter["chapter_id"]): chapter for chapter in framework["chapters"]}
    kinds = {
        str(block.get("kind") or "")
        for chapter in (by_id["0"], by_id["4"], by_id["6"])
        for block in (chapter.get("body") or [])
        if isinstance(block, dict)
    }
    assert "decision_questions" in kinds
    assert "today_vs_agent" in kinds
    assert "building_blocks" in kinds


def test_blackbox_eval_does_not_echo_opportunity_identifiers() -> None:
    framework = _generate()
    blob = json.dumps(framework.get("open_items") or [])
    assert "061985" not in blob
    assert "OPP-061985" not in blob


def test_blackbox_eval_is_deterministic_across_two_runs() -> None:
    first = _generate()
    second = _generate()
    assert [(str(ch["chapter_id"]), ch["title"]) for ch in first["chapters"]] == [
        (str(ch["chapter_id"]), ch["title"]) for ch in second["chapters"]
    ]
    assert first["open_items"] == second["open_items"]
    assert first["business_case"]["grounded"] == second["business_case"]["grounded"]
    assert first["quality_scores"] == second["quality_scores"]
    assert json.dumps(first["chapters"], sort_keys=True) == json.dumps(second["chapters"], sort_keys=True)
