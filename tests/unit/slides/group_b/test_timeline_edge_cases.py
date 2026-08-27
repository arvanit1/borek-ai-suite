"""JJ-21: TIMELINE_01 edge cases — single phase, maximum phases, overlapping date ranges."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EDGE_TEST = (
    ROOT / "apps" / "renderer" / "layouts" / "group_b" / "renderTimeline01.edge.test.ts"
)


def test_jj21_timeline_edge_case_module_exists() -> None:
    assert EDGE_TEST.is_file(), f"expected timeline edge-case tests at {EDGE_TEST}"
    source = EDGE_TEST.read_text(encoding="utf-8")
    assert "single" in source.casefold()
    assert "maximum" in source.casefold()
    assert "overlap" in source.casefold()


def test_jj21_timeline_edge_cases() -> None:
    result = subprocess.run(
        "npm run test:jj21 --workspace borek-renderer",
        cwd=ROOT,
        check=False,
        shell=True,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
