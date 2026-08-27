"""BT-24: Group A golden-deck fixture and regression wiring checks."""

from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GROUP_A_DIR = ROOT / "tests" / "golden_deck" / "group_a"

REFERENCE_FILES = tuple(f"slide-{index:02d}.png" for index in range(1, 6))
LAYOUT_IDS = (
    "COVER_01",
    "CONTEXT_01",
    "PROBLEM_SOLUTION_01",
    "SCOPE_01",
    "REQUIREMENTS_MATRIX_01",
)


def test_bt24_group_a_reference_assets_exist() -> None:
    for file_name in REFERENCE_FILES:
        path = GROUP_A_DIR / file_name
        assert path.is_file(), file_name
        assert path.stat().st_size > 0
        assert _png_size(path) == (2001, 1125)


def test_bt24_group_a_manifest_maps_all_layouts() -> None:
    source = (GROUP_A_DIR / "fixtures.ts").read_text(encoding="utf-8")
    for layout_id in LAYOUT_IDS:
        assert layout_id in source
    for file_name in REFERENCE_FILES:
        slide_number = int(file_name[6:8])
        assert f"slideFileName({slide_number})" in source
    assert source.count('with { type: "json" }') == 5
    assert source.count('sourceFixture: "') == 5


def test_bt24_uses_production_dispatcher_and_at55_runner() -> None:
    deck_source = (GROUP_A_DIR / "build_deck.ts").read_text(encoding="utf-8")
    test_source = (GROUP_A_DIR / "run_regression.test.ts").read_text(encoding="utf-8")
    assert "dispatchSlide" in deck_source
    assert "compareGoldenDeck" in test_source
    assert "runGoldenDeckRegression" in test_source
    assert '"--expected-count"' in test_source


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])
