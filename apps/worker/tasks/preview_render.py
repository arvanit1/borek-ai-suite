"""AT-9 worker entrypoint for LibreOffice preview generation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PREVIEW_CLI = ROOT / "apps" / "renderer" / "scripts" / "run_preview_pipeline.ts"


def run_preview_render(pptx_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Run shared AT-9 preview pipeline via the renderer CLI."""
    pptx = Path(pptx_path).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["npx", "tsx", str(PREVIEW_CLI), str(pptx), str(output)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "preview pipeline failed").strip()
        raise RuntimeError(message)

    return json.loads(result.stdout)
