"""Presentation CI contract — colors, geometry, theme, logo, voice."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.presentation.ci_contract import (
    banned_marketing_terms,
    ci_voice_instruction_block,
    load_presentation_ci,
    official_gamma_theme_id,
)

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3] / "packages" / "contracts" / "presentation_ci.json"
)


def test_presentation_ci_contract_loads() -> None:
    ci = load_presentation_ci()
    assert ci["schema_version"] == "1.0"
    assert official_gamma_theme_id() == "y7pjh5eetjgbiym"


def test_presentation_ci_colors_match_brand_guide() -> None:
    colors = load_presentation_ci()["colors"]
    assert colors["primary"]["hex"] == "#0D1240"
    assert colors["paper"]["hex"] == "#FFFFFF"
    assert colors["mist"]["hex"] == "#F3F4F8"
    assert colors["slate"]["hex"] == "#5C6178"
    assert colors["hairline"]["hex"] == "#E2E4EC"
    assert colors["spirit"]["hex"] == "#124F94"
    assert set(colors["splash"]["allowed"]) == {
        "#E07E00",
        "#DD3D00",
        "#124F94",
        "#02A69F",
    }


def test_presentation_ci_geometry_and_logo_policy() -> None:
    ci = load_presentation_ci()
    geometry = ci["geometry"]
    assert geometry["aspect_ratio"] == "16:9"
    assert geometry["design_width_px"] == 1920
    assert geometry["design_height_px"] == 1080
    assert geometry["margin_px"] == 120
    assert geometry["corner_radius_px"] == 0
    assert geometry["slides"]["content"]["borek_logo"] is False
    assert geometry["slides"]["cover"]["borek_logo"] is True
    assert ci["logo"]["borek_logo_on_content_slides"] is False


def test_presentation_ci_typography_and_voice() -> None:
    ci = load_presentation_ci()
    typography = ci["typography"]
    assert typography["primary_family"] == "Inter"
    assert typography["minimum_slide_text_px"] == 24
    voice = ci["voice"]
    assert voice["no_emoji"] is True
    assert voice["no_exclamation_marks"] is True
    assert "leverage" in banned_marketing_terms()
    assert "synergy" in banned_marketing_terms()
    assert "best-in-class" in banned_marketing_terms()


def test_ci_voice_instruction_block_references_banned_terms() -> None:
    block = ci_voice_instruction_block()
    assert "leverage" in block
    assert "No exclamation marks" in block
    assert "takeaway" in block.lower()


def test_presentation_ci_json_is_valid_on_disk() -> None:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert payload["official_gamma_theme_id"] == official_gamma_theme_id()


@pytest.mark.parametrize("term", banned_marketing_terms())
def test_each_banned_term_is_non_empty(term: str) -> None:
    assert term.strip()
