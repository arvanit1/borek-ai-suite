"""JJ-22: Group B golden-deck fixtures wired into the AT-55 regression runner."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DECK_DIR = ROOT / "tests" / "golden_deck"
GROUP_B_DIR = GOLDEN_DECK_DIR / "group_b"

GROUP_B_REFERENCES = (
    "process_flow_01.png",
    "timeline_01.png",
    "milestones_01.png",
    "team_fte_01.png",
)


def test_jj22_group_b_reference_renderings_exist() -> None:
    for file_name in GROUP_B_REFERENCES:
        path = GROUP_B_DIR / file_name
        assert path.is_file(), file_name
        assert path.stat().st_size > 0


def test_jj22_regression_runner_lists_group_b_files() -> None:
    source = (GOLDEN_DECK_DIR / "compare.ts").read_text(encoding="utf-8")
    assert "GROUP_B_GOLDEN_FILES" in source
    assert "listGoldenDeckFiles" in source
    runner = (GOLDEN_DECK_DIR / "run_regression.ts").read_text(encoding="utf-8")
    assert "listGoldenDeckFiles" in runner
    for file_name in GROUP_B_REFERENCES:
        assert file_name in source


def test_jj22_group_b_golden_deck_regression() -> None:
    result = subprocess.run(
        "npm run test:jj22 --workspace borek-renderer",
        cwd=ROOT,
        check=False,
        shell=True,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
