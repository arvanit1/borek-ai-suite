"""ES-39 / SUCCESS_METRICS_01 commercial exclusion repair tests."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from services.slides.content_generation.group_c.common import (
    ProhibitedCommercialContentError,
    StructuredGenerationRequest,
    repair_excluded_monetary_content,
)
from services.slides.content_generation.group_c.success_metrics_01 import (
    CONFIG,
    generate_success_metrics_01,
)

ROOT = Path(__file__).resolve().parents[4]
FRAMEWORK_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_c.json"
SLIDE_FIXTURE_PATH = (
    ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "success_metrics_01.minimal.json"
)


@dataclass
class CapturingGenerator:
    output: dict[str, Any]
    requests: list[StructuredGenerationRequest] = field(default_factory=list)

    def __call__(self, request: StructuredGenerationRequest) -> dict[str, Any]:
        self.requests.append(request)
        return copy.deepcopy(self.output)


def _framework() -> dict[str, Any]:
    return json.loads(FRAMEWORK_FIXTURE_PATH.read_text(encoding="utf-8"))


def _slide() -> dict[str, Any]:
    return json.loads(SLIDE_FIXTURE_PATH.read_text(encoding="utf-8"))


def _chapters() -> tuple[dict[str, Any], ...]:
    framework = _framework()
    by_id = {chapter["chapter_id"]: chapter for chapter in framework["chapters"]}
    return tuple(
        {
            "chapter_id": chapter_id,
            "title": by_id[chapter_id]["title"],
            "body": copy.deepcopy(by_id[chapter_id]["body"]),
        }
        for chapter_id in ("3", "9")
    )


def _run(slide_spec: dict[str, Any]):
    return generate_success_metrics_01(
        _framework(),
        structured_generate=CapturingGenerator(output=slide_spec),
        compress_fields=lambda values, violations: values,
    )


def test_subtitle_commercial_content_is_removed() -> None:
    slide = _slide()
    slide["subtitle"] = "Reduce annual cost by €125,000"

    result = _run(slide)

    assert result.status == "VALID"
    assert "subtitle" not in result.slide_spec


def test_non_commercial_subtitle_is_preserved() -> None:
    slide = _slide()
    slide["subtitle"] = "Measure operational reliability and adoption"
    slide["fieldProvenance"].append(
        {"path": "subtitle", "sourceChapterIds": ["3"]}
    )

    result = _run(slide)

    assert result.status == "VALID"
    assert result.slide_spec["subtitle"] == "Measure operational reliability and adoption"


def test_metric_commercial_language_is_repaired() -> None:
    slide = _slide()
    slide["criteria"][0]["description"] = "Increase ROI and reduce licensing spend"

    result = _run(slide)

    assert result.status == "VALID"
    description = result.slide_spec["criteria"][0]["description"]
    assert "ROI" not in description.casefold()
    assert "licensing spend" not in description.casefold()


def test_commercial_language_without_currency_symbol_is_excluded() -> None:
    slide = _slide()
    slide["subtitle"] = "Increase ROI and reduce licensing spend"

    result = _run(slide)

    assert result.status == "VALID"
    assert "subtitle" not in result.slide_spec


def test_repair_helper_preserves_non_commercial_content() -> None:
    slide = _slide()
    slide["subtitle"] = "Measure operational reliability and adoption"

    repaired = repair_excluded_monetary_content(slide, chapters=_chapters())

    assert repaired["subtitle"] == "Measure operational reliability and adoption"


def test_full_generation_with_live_style_commercial_subtitle() -> None:
    slide = _slide()
    slide["subtitle"] = "Reduce annual cost by €125,000"

    result = _run(slide)

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert "€" not in json.dumps(result.slide_spec)


def test_prompt_includes_explicit_monetary_exclusion_rule() -> None:
    generator = CapturingGenerator(output=_slide())
    generate_success_metrics_01(
        _framework(),
        structured_generate=generator,
        compress_fields=lambda values, violations: values,
    )

    assert "excludeMonetaryFields=true" in generator.requests[0].instructions
    assert "pricing language" in generator.requests[0].instructions


def test_commercial_title_is_replaced_with_grounded_fallback() -> None:
    slide = _slide()
    slide["title"] = "ROI payback budget investment revenue pricing"

    result = _run(slide)

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["title"] == "Aim & success measurement"


def test_architecture_layout_config_does_not_enable_monetary_repair() -> None:
    from services.slides.content_generation.group_c.architecture_01 import CONFIG as ARCH_CONFIG

    assert ARCH_CONFIG.exclude_monetary_fields is False
