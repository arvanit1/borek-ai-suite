"""ES-35 — shared eval transcript set with expected-behavior notes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.transcript.ingestion import ingest_transcript
from services.transcript.speaker_turns import split_speaker_turns

ROOT = Path(__file__).resolve().parents[3]
EVAL = ROOT / "tests" / "eval" / "framework"
REQUIRED_BEHAVIOR_KEYS = (
    "summary",
    "must_extract_topics",
    "must_surface_open_items",
    "must_detect_contradiction",
    "must_flag_multi_process",
    "conversation_quality_band",
    "build_readiness_band",
    "chapter_focus",
    "eval_notes",
)
QUALITY_BANDS = frozenset({"strong", "usable", "needs_human_followup"})
READINESS_BANDS = frozenset({"ready_to_build", "ready_with_assumptions", "not_ready"})


def _load_manifest() -> dict:
    return json.loads((EVAL / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def manifest() -> dict:
    return _load_manifest()


def test_es35_manifest_lists_ten_to_twenty_cases(manifest: dict) -> None:
    assert manifest["ticket"] == "ES-35"
    assert 10 <= len(manifest["cases"]) <= 20
    assert len(manifest["cases"]) == 15


def test_es35_quality_tiers_are_documented(manifest: dict) -> None:
    documented = set(manifest["quality_tiers"])
    used = {case["quality_tier"] for case in manifest["cases"]}
    assert used.issubset(documented)


@pytest.mark.parametrize("case", _load_manifest()["cases"], ids=lambda item: item["id"])
def test_es35_transcript_exists_and_ingests(case: dict) -> None:
    transcript_path = ROOT / case["transcript"]
    assert transcript_path.is_file(), f"Missing transcript: {transcript_path}"
    content = transcript_path.read_bytes()
    result = ingest_transcript(transcript_path.name, content)
    assert result.normalized_text.strip()
    turns = split_speaker_turns(transcript_path.name, content)
    assert turns, f"No speaker turns parsed for {case['id']}"
    assert len(turns) >= 2


@pytest.mark.parametrize("case", _load_manifest()["cases"], ids=lambda item: item["id"])
def test_es35_expected_behavior_notes_are_complete(case: dict) -> None:
    behavior = case["expected_behavior"]
    for key in REQUIRED_BEHAVIOR_KEYS:
        assert key in behavior, f"{case['id']} missing expected_behavior.{key}"
    assert behavior["summary"].strip()
    assert isinstance(behavior["must_extract_topics"], list)
    assert behavior["must_extract_topics"]
    assert isinstance(behavior["chapter_focus"], list)
    assert behavior["chapter_focus"]
    assert behavior["eval_notes"].strip()
    assert behavior["conversation_quality_band"] in QUALITY_BANDS
    assert behavior["build_readiness_band"] in READINESS_BANDS
    assert isinstance(behavior["must_surface_open_items"], bool)
    assert isinstance(behavior["must_detect_contradiction"], bool)
    assert isinstance(behavior["must_flag_multi_process"], bool)


def test_es35_includes_varying_quality_tiers(manifest: dict) -> None:
    tiers = {case["quality_tier"] for case in manifest["cases"]}
    assert "rich" in tiers
    assert "sparse" in tiers
    assert "contradictory" in tiers
    assert len(tiers) >= 4


def test_es35_references_es33_fixtures(manifest: dict) -> None:
    overlap = [case for case in manifest["cases"] if case.get("es33_overlap")]
    assert len(overlap) == 3
    ids = {case["id"] for case in overlap}
    assert ids == {"invoice_3way_match", "minimal_invoice_match", "warehouse_delivery_match"}


def test_es35_new_transcripts_live_under_framework_folder(manifest: dict) -> None:
    local = [
        case
        for case in manifest["cases"]
        if str(case["transcript"]).startswith("tests/eval/framework/transcripts/")
    ]
    assert len(local) == 12
