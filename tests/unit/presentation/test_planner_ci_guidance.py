"""Planner prompt includes CI editorial guidance without breaking localization."""

from __future__ import annotations

from pathlib import Path

from services.presentation.planner import PROMPT_PATH


def test_planner_prompt_includes_ci_editorial_guidance() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "one clear idea per slide" in prompt.lower()
    assert "takeaway" in prompt.lower()
    assert "success_metrics" in prompt.lower()
    assert "leverage" in prompt.lower()
    assert "emoji" in prompt.lower()


def test_planner_prompt_preserves_german_localization_rules() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "presentationRenderLanguage=de" in prompt
    assert "customerLocalizedChapters" in prompt
    assert "frameworkReferences" in prompt
