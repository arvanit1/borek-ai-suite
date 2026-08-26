"""ES-34 live — optional Claude API runs on ES-33 fixtures (not for default CI).

Run manually when ANTHROPIC_API_KEY is set:

    pytest tests/integration/extraction_synthesis/test_es34_live_pipeline.py -m live_claude -v

Or a single case (~2 Claude calls):

    pytest tests/integration/extraction_synthesis/test_es34_live_pipeline.py -m live_claude -k minimal -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.framework.chapter_validators import validate_all_chapters
from services.framework.synthesis import PROMPT_VERSION as SYNTHESIS_PROMPT_VERSION
from services.knowledge_model.extraction import KNOWLEDGE_BUCKETS, PROMPT_VERSION as EXTRACTION_PROMPT_VERSION
from services.knowledge_model.source_refs import (
    collect_customer_report_source_ref_violations,
    validate_source_refs,
)

from helpers import load_manifest, run_es34_live_pipeline

pytestmark = pytest.mark.live_claude

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = json.loads((ROOT / "packages" / "contracts" / "chapter_registry.json").read_text(encoding="utf-8"))
CASES = load_manifest()["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda item: item["id"])
def test_es34_live_pipeline_end_to_end(case: dict, anthropic_api_key: str) -> None:
    """One live extraction + synthesis run per ES-33 case (2 Claude calls)."""
    _ = anthropic_api_key
    run = run_es34_live_pipeline(case)
    framework = run.framework
    model = run.knowledge_model

    expected_titles = [(item["chapter_id"], item["title"]) for item in REGISTRY["chapters"]]
    actual_titles = [(str(ch["chapter_id"]), ch["title"]) for ch in framework["chapters"]]
    assert len(framework["chapters"]) == 14
    assert actual_titles == expected_titles
    assert framework["generation_meta"]["llm_used"] is True
    assert framework["generation_meta"]["prompt_version"] == SYNTHESIS_PROMPT_VERSION
    assert model["prompt_version"] == EXTRACTION_PROMPT_VERSION

    assert validate_all_chapters(framework) == []

    validate_source_refs(model)
    conversation_ids = {model["conversation_id"]}
    assert (
        collect_customer_report_source_ref_violations(
            {"chapters": framework["chapters"]},
            allowed_conversation_ids=sorted(conversation_ids),
        )
        == []
    )
    for chapter in framework["chapters"]:
        refs = chapter.get("source_refs") or []
        assert refs, f"Chapter {chapter['chapter_id']} is missing source_refs"

    scores = framework["quality_scores"]
    for gate in ("opportunity_rating", "conversation_quality", "build_readiness"):
        value = scores[gate]
        assert isinstance(value, int)
        assert 0 <= value <= 100
        assert f"{value}/100" in scores["rationale"][gate]

    for bucket in KNOWLEDGE_BUCKETS:
        assert isinstance(model.get(bucket), list)
    assert model["facts"], "Live extraction should surface at least one fact from the transcript."
