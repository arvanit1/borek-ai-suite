"""ES-30 — synthesis system prompt assembled from template, schema, checklist, tone config."""

from __future__ import annotations

from services.framework.config_loader import tone_voice
from services.framework.synthesis import PROMPT_VERSION, build_synthesis_system_prompt


def test_es30_prompt_includes_role_schema_checklist_titles_and_config_tone() -> None:
    prompt = build_synthesis_system_prompt()
    guide = tone_voice()

    assert PROMPT_VERSION in prompt
    assert "CUSTOMER Framework Report" in prompt
    assert "SCHEMA CONTRACT" in prompt
    assert "CustomerReportDraft" in prompt
    assert "submit_customer_report" in prompt
    assert "CHAPTER CHECKLIST" in prompt
    assert "About this document" in prompt
    assert "Trustworthiness" in prompt
    assert "CHAPTER TITLES" in prompt
    assert "0. About this document" in prompt
    assert "13. Next steps & glossary" in prompt

    assert "STYLE & GUARDRAILS" in prompt
    assert "config/tone_voice.yaml" in prompt
    assert guide["style"] in prompt
    assert guide["audience"] in prompt
    for item in guide["must"]:
        assert item in prompt
    for item in guide["must_not"]:
        assert item in prompt


def test_es30_prompt_includes_es13_cross_chapter_ai_consistency() -> None:
    prompt = build_synthesis_system_prompt()
    assert "CROSS-CHAPTER AI CONSISTENCY" in prompt
    assert "ES-13 confirm gate" in prompt
    assert "CONFIRM GATE (ES-13)" in prompt
    assert "ai_split is the ONLY canonical list" in prompt
    assert "prepares approval" in prompt
    assert "Do not repeat chapter 6 ai_split not_used_for" in prompt


def test_es30_tone_is_not_hardcoded_json_dump() -> None:
    prompt = build_synthesis_system_prompt()
    assert '"must_not"' not in prompt
    assert '"chapter_checklist"' not in prompt
