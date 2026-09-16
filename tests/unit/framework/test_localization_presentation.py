"""ES-32 localization must reach Stage B planning and SlideSpec generation."""

from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path

import pytest

from services.framework.customer_view import (
    build_customer_view,
    localized_planning_chapters,
    presentation_chapter_excerpt,
    presentation_render_language,
    resolve_customer_view,
)
from services.framework.pipeline import generate_customer_framework
from services.framework.pre_confirm_check import confirm_customer_report
from services.presentation.planner import plan_presentation
from services.slides.content_generation.group_a.common import _extract_allowed_chapters

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures"


@pytest.fixture(autouse=True)
def _deterministic_localize(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = lambda **_kwargs: _german_localize
    monkeypatch.setattr("services.framework.localization.make_localize_fn", stub)
    pre_confirm_module = importlib.import_module("services.framework.pre_confirm_check")
    monkeypatch.setattr(pre_confirm_module, "make_localize_fn", stub)


def _golden_framework() -> dict:
    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    overrides = json.loads((FIXTURES / "engine_overrides.invoice_3way.json").read_text(encoding="utf-8"))
    return generate_customer_framework(
        [model],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )


def _german_localize(_system: str, user: str, _schema: dict) -> dict:
    payload = json.loads(user.split("JSON:\n", 1)[1])
    for chapter in payload.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        if chapter.get("title"):
            chapter["title"] = f"DE — {chapter['title']}"
        for block in chapter.get("body") or []:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                block["text"] = f"DE — {block['text']}"
        if str(chapter.get("chapter_id")) == "5":
            body = chapter.setdefault("body", [])
            body.append(
                {
                    "block": "callout",
                    "kind": "important",
                    "text": (
                        "Bei Ausnahmen entscheiden Menschen — der Agent ist "
                        "gegenüber Lieferanten niemals autonom."
                    ),
                }
            )
    review = payload.setdefault("review_summary", {})
    if isinstance(review.get("executive_summary"), str):
        review["executive_summary"] = f"DE — {review['executive_summary']}"
    return payload


def _german_draft() -> dict:
    framework = _golden_framework()
    framework["customer_view"] = build_customer_view(
        framework,
        lang="de",
        localize=_german_localize,
    )
    return framework


class _CapturePlanner:
    def __init__(self) -> None:
        self.planning_input: dict | None = None

    def complete_planning(self, *, planning_input=None, **_kwargs):
        self.planning_input = planning_input or {}
        return {
            "schema_version": "1.0",
            "title": "Plan",
            "slides": [
                {
                    "order": 1,
                    "purpose": "context",
                    "layoutId": "CONTEXT_01",
                    "frameworkReferences": ["chapter_1", "chapter_2"],
                }
            ],
        }


def test_confirm_rebuilds_german_customer_view_with_localize() -> None:
    draft = _german_draft()
    draft["customer_view"] = {"render_language": "de", "chapters": draft["chapters"]}
    confirmed = confirm_customer_report(draft)
    view = confirmed["customer_view"]
    assert view["render_language"] == "de"
    assert str(view["chapters"][0]["title"]).startswith("DE —")
    assert confirmed["chapters"][0]["title"] != view["chapters"][0]["title"]


def test_canonical_language_master_stays_english() -> None:
    confirmed = confirm_customer_report(_german_draft())
    assert confirmed["language_master"] == "en"
    assert confirmed["chapters"][0]["title"] == _golden_framework()["chapters"][0]["title"]


def test_presentation_chapter_excerpt_uses_localized_prose() -> None:
    confirmed = confirm_customer_report(_german_draft())
    assert presentation_render_language(confirmed) == "de"
    excerpt = presentation_chapter_excerpt(confirmed, "1")
    assert excerpt["title"].startswith("DE —")
    assert confirmed["chapters"][1]["title"] != excerpt["title"]


def test_planner_receives_german_customer_chapters(monkeypatch: pytest.MonkeyPatch) -> None:
    confirmed = confirm_customer_report(_german_draft())
    confirmed["status"] = "confirmed"
    planner = _CapturePlanner()
    plan_presentation(confirmed, planner=planner)
    assert planner.planning_input is not None
    localized = planner.planning_input.get("customerLocalizedChapters") or []
    assert localized[0]["title"].startswith("DE —")
    assert planner.planning_input.get("presentationRenderLanguage") == "de"


def test_slide_generation_uses_german_chapters() -> None:
    confirmed = confirm_customer_report(_german_draft())
    confirmed["status"] = "confirmed"
    chapters = _extract_allowed_chapters(confirmed, ("1", "2"))
    assert chapters[0]["title"].startswith("DE —")


def test_english_opportunity_unchanged() -> None:
    framework = _golden_framework()
    framework["status"] = "confirmed"
    assert localized_planning_chapters(framework) == []
    excerpt = presentation_chapter_excerpt(framework, "1")
    assert excerpt["title"] == framework["chapters"][1]["title"]


def test_german_chapter_five_autonomy_preserved_in_customer_view() -> None:
    confirmed = confirm_customer_report(_german_draft())
    ch5 = next(
        chapter
        for chapter in confirmed["customer_view"]["chapters"]
        if str(chapter.get("chapter_id")) == "5"
    )
    ch5_blob = json.dumps(ch5, ensure_ascii=False).lower()
    assert "niemals autonom" in ch5_blob
    canonical_ch5 = next(
        chapter
        for chapter in confirmed["chapters"]
        if str(chapter.get("chapter_id")) == "5"
    )
    assert canonical_ch5["body"] != ch5["body"]


def test_resolve_customer_view_refreshes_english_tagged_de_cache() -> None:
    framework = _golden_framework()
    framework["customer_view"] = {
        "render_language": "de",
        "customer_only": True,
        "chapters": copy.deepcopy(framework["chapters"]),
    }
    refreshed = resolve_customer_view(framework, lang="de", localize=_german_localize)
    assert refreshed["chapters"][0]["title"].startswith("DE —")


def test_localization_metadata_survives_confirm() -> None:
    confirmed = confirm_customer_report(_german_draft())
    assert confirmed["customer_view"]["render_language"] == "de"
    assert confirmed["customer_view"].get("customer_only") is True
