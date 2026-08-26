"""ES-34 — automated extraction + synthesis pipeline tests on ES-33 fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.framework.chapter_validators import validate_all_chapters
from services.framework.synthesis import PROMPT_VERSION as SYNTHESIS_PROMPT_VERSION
from services.knowledge_model.extraction import PROMPT_VERSION as EXTRACTION_PROMPT_VERSION
from services.knowledge_model.source_refs import (
    collect_customer_report_source_ref_violations,
    collect_knowledge_model_source_ref_violations,
    validate_source_refs,
)

from helpers import load_json, load_manifest, run_es34_pipeline

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = json.loads((ROOT / "packages" / "contracts" / "chapter_registry.json").read_text(encoding="utf-8"))
MANIFEST = load_manifest()
CASES = MANIFEST["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda item: item["id"])
def test_es34_pipeline_runs_extraction_and_synthesis_once(case: dict) -> None:
    run = run_es34_pipeline(case)
    assert run.extraction_calls == 1
    assert run.synthesis_calls == 1
    assert run.framework["generation_meta"]["llm_used"] is True
    assert run.framework["generation_meta"]["prompt_version"] == SYNTHESIS_PROMPT_VERSION
    assert run.knowledge_model["prompt_version"] == EXTRACTION_PROMPT_VERSION


@pytest.mark.parametrize("case", CASES, ids=lambda item: item["id"])
def test_es34_pipeline_has_all_fourteen_registry_chapters(case: dict) -> None:
    run = run_es34_pipeline(case)
    framework = run.framework
    expected_titles = [(item["chapter_id"], item["title"]) for item in REGISTRY["chapters"]]
    actual_titles = [(str(ch["chapter_id"]), ch["title"]) for ch in framework["chapters"]]
    assert len(framework["chapters"]) == 14
    assert actual_titles == expected_titles


@pytest.mark.parametrize("case", CASES, ids=lambda item: item["id"])
def test_es34_pipeline_passes_chapter_validators_es14_through_es27(case: dict) -> None:
    run = run_es34_pipeline(case)
    issues = validate_all_chapters(run.framework)
    assert issues == []


@pytest.mark.parametrize("case", CASES, ids=lambda item: item["id"])
def test_es34_pipeline_knowledge_model_has_valid_source_refs(case: dict) -> None:
    run = run_es34_pipeline(case)
    validate_source_refs(run.knowledge_model)
    assert collect_knowledge_model_source_ref_violations(run.knowledge_model) == []


@pytest.mark.parametrize("case", CASES, ids=lambda item: item["id"])
def test_es34_pipeline_chapters_have_source_refs(case: dict) -> None:
    run = run_es34_pipeline(case)
    conversation_ids = {run.knowledge_model["conversation_id"]}
    violations = collect_customer_report_source_ref_violations(
        {"chapters": run.framework["chapters"]},
        allowed_conversation_ids=sorted(conversation_ids),
    )
    assert violations == []
    for chapter in run.framework["chapters"]:
        refs = chapter.get("source_refs") or []
        assert refs, f"Chapter {chapter['chapter_id']} is missing source_refs"
        for ref in refs:
            assert ref.get("conversation_id")
            assert ref.get("excerpt_pointer")
            assert ref.get("speaker_role")


@pytest.mark.parametrize("case", CASES, ids=lambda item: item["id"])
def test_es34_pipeline_quality_scores_match_expected(case: dict) -> None:
    run = run_es34_pipeline(case)
    expected = load_json(case["expected_framework"])
    actual = run.framework["quality_scores"]
    expected_scores = expected["quality_scores"]
    assert actual["opportunity_rating"] == expected_scores["opportunity_rating"]
    assert actual["conversation_quality"] == expected_scores["conversation_quality"]
    assert actual["build_readiness"] == expected_scores["build_readiness"]
    for gate in ("opportunity_rating", "conversation_quality", "build_readiness"):
        assert actual["rationale"][gate] == expected_scores["rationale"][gate]
