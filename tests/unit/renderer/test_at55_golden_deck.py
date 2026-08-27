"""AT-55: golden-deck regression runner contract tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DECK_DIR = ROOT / "tests" / "golden_deck"
REFERENCE_DIR = GOLDEN_DECK_DIR / "reference"

REQUIRED_FILES = (
    "compare.ts",
    "fixtures.ts",
    "run_regression.ts",
    "run_regression.test.ts",
    "build_reference.ts",
)

DIFF_CATEGORIES = ("spacing", "font", "alignment", "color")


def test_at55_golden_deck_modules_exist() -> None:
    for file_name in REQUIRED_FILES:
        assert (GOLDEN_DECK_DIR / file_name).is_file(), file_name


def test_at55_reference_rendering_exists() -> None:
    reference_png = REFERENCE_DIR / "slide-01.png"
    assert reference_png.is_file()
    assert reference_png.stat().st_size > 0


def test_at55_compare_module_declares_diff_categories() -> None:
    source = (GOLDEN_DECK_DIR / "compare.ts").read_text(encoding="utf-8")
    for category in DIFF_CATEGORIES:
        assert category in source


def test_at55_runner_supports_reference_and_actual_comparison() -> None:
    source = (GOLDEN_DECK_DIR / "run_regression.ts").read_text(encoding="utf-8")
    assert "compareGoldenDeck" in source
    assert "--reference" in source
    assert "--actual" in source
    assert "runLibreOfficePreviewPipeline" in source
    assert "listGoldenDeckFiles" in source
