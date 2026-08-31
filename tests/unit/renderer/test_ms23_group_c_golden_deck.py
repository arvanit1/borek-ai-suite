"""MS-23: Group C golden-deck fixture and regression wiring checks."""

from __future__ import annotations

import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GROUP_C_DIR = ROOT / "tests" / "golden_deck" / "group_c"

REFERENCE_FILES = tuple(f"slide-{index:02d}.png" for index in range(1, 6))
LAYOUT_IDS = (
    "ARCHITECTURE_01",
    "COMPLIANCE_01",
    "SUCCESS_METRICS_01",
    "OPEN_QUESTIONS_01",
    "NEXT_STEPS_01",
)


def test_ms23_group_c_reference_assets_exist() -> None:
    for file_name in REFERENCE_FILES:
        path = GROUP_C_DIR / file_name
        assert path.is_file(), file_name
        assert path.stat().st_size > 0
        assert _png_size(path) == (2001, 1125)


def test_ms23_group_c_manifest_maps_all_layouts() -> None:
    source = (GROUP_C_DIR / "fixtures.ts").read_text(encoding="utf-8")
    for layout_id in LAYOUT_IDS:
        assert layout_id in source
    for file_name in REFERENCE_FILES:
        slide_number = int(file_name[6:8])
        assert f"slideFileName({slide_number})" in source
    assert source.count('with { type: "json" }') == 5
    assert source.count('sourceFixture: "') == 5


def test_ms23_uses_production_dispatcher_and_at55_runner() -> None:
    deck_source = (GROUP_C_DIR / "build_deck.ts").read_text(encoding="utf-8")
    test_source = (GROUP_C_DIR / "run_regression.test.ts").read_text(encoding="utf-8")
    assert "dispatchSlide" in deck_source
    assert "registerMasterClosing" in deck_source
    assert "compareGoldenDeck" in test_source
    assert "runGoldenDeckRegression" in test_source
    assert '"--expected-count"' in test_source


def test_ms23_group_c_golden_deck_regression() -> None:
    result = subprocess.run(
        "npm run test:ms23 --workspace borek-renderer",
        cwd=ROOT,
        check=False,
        shell=True,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])
