"""ES-33 — eval fixture transcript set with hand-verified FrameworkObject outputs."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from services.framework.pipeline import generate_customer_framework

ROOT = Path(__file__).resolve().parents[3]
EVAL = ROOT / "tests" / "eval" / "fixtures"
FROZEN_AT = "2026-08-26T10:00:00Z"


def _load_manifest() -> dict:
    return json.loads((EVAL / "manifest.json").read_text(encoding="utf-8"))


def _normalize(framework: dict, *, opportunity_id: str) -> dict:
    framework = json.loads(json.dumps(framework))
    framework.pop("customer_view", None)
    framework_id = f"FW-{opportunity_id}-v1"
    framework["id"] = framework_id
    framework["framework_id"] = framework_id
    framework["created_at"] = FROZEN_AT
    framework["updated_at"] = FROZEN_AT
    meta = framework.get("generation_meta") or {}
    meta["generated_at"] = FROZEN_AT
    meta["llm_job_log"] = []
    meta["llm_used"] = False
    meta["llm_model"] = "deterministic-builder"
    framework["generation_meta"] = meta
    return framework


@pytest.fixture(scope="module")
def framework_schema() -> dict:
    return json.loads((ROOT / "packages" / "contracts" / "framework_object.schema.json").read_text(encoding="utf-8"))


def test_es33_manifest_lists_three_verified_cases() -> None:
    manifest = _load_manifest()
    assert manifest["ticket"] == "ES-33"
    assert 2 <= len(manifest["cases"]) <= 3
    assert len(manifest["cases"]) == 3


@pytest.mark.parametrize("case", _load_manifest()["cases"], ids=lambda item: item["id"])
def test_es33_expected_files_exist_with_fourteen_chapters(case: dict) -> None:
    transcript = ROOT / case["transcript"]
    expected = ROOT / case["expected_framework"]
    assert transcript.is_file(), f"Missing transcript: {transcript}"
    assert expected.is_file(), f"Missing expected framework: {expected}"
    framework = json.loads(expected.read_text(encoding="utf-8"))
    assert len(framework["chapters"]) == 14
    chapter_ids = [str(item["chapter_id"]) for item in framework["chapters"]]
    assert chapter_ids == [str(index) for index in range(14)]


@pytest.mark.parametrize("case", _load_manifest()["cases"], ids=lambda item: item["id"])
def test_es33_expected_validates_against_framework_schema(case: dict, framework_schema: dict) -> None:
    framework = json.loads((ROOT / case["expected_framework"]).read_text(encoding="utf-8"))
    jsonschema.validate(instance=framework, schema=framework_schema)


@pytest.mark.parametrize("case", _load_manifest()["cases"], ids=lambda item: item["id"])
def test_es33_expected_matches_deterministic_pipeline(case: dict) -> None:
    model = json.loads((ROOT / case["knowledge_model"]).read_text(encoding="utf-8"))
    overrides = json.loads((ROOT / case["engine_overrides"]).read_text(encoding="utf-8"))
    expected = json.loads((ROOT / case["expected_framework"]).read_text(encoding="utf-8"))
    actual = generate_customer_framework(
        [model],
        opportunity_id=case["opportunity_id"],
        title_hint=case["title_hint"],
        use_llm=False,
        engine_overrides=overrides,
    )
    actual = _normalize(actual, opportunity_id=case["opportunity_id"])
    assert actual == expected
