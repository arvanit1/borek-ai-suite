"""AT-10 worker entrypoint for render validation checks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RENDER_CHECKS_CLI = ROOT / "apps" / "renderer" / "scripts" / "run_render_checks.ts"


def run_render_validation(
    presentation_plan_path: str | Path,
    preview_result_path: str | Path,
) -> dict[str, Any]:
    """Run shared AT-10 render checks via the renderer CLI."""
    plan = Path(presentation_plan_path).resolve()
    preview = Path(preview_result_path).resolve()

    result = subprocess.run(
        ["npx", "tsx", str(RENDER_CHECKS_CLI), str(plan), str(preview)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        message = (result.stderr or result.stdout or "render checks failed").strip()
        raise RuntimeError(message)

    payload = json.loads(result.stdout)
    if result.returncode == 1 and payload.get("status") != "VALIDATION_FAILED":
        raise RuntimeError((result.stderr or result.stdout or "render checks failed").strip())
    return payload
