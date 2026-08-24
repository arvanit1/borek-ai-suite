#!/usr/bin/env python3
"""Client delivery gate: schema tickets (AT-1..AT-9) and codegen checks must pass."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, shell: bool = False) -> None:
    print("+", " ".join(command) if isinstance(command, list) else command)
    subprocess.run(command, cwd=ROOT, check=True, shell=shell)


def main() -> int:
    run([sys.executable, "-m", "pytest", "tests/unit", "-v"])
    run([sys.executable, "scripts/generate_pydantic.py"])
    run(["node", "scripts/generate_typescript.js"])
    run([sys.executable, "-c", "import generated.python.contracts.framework_object as fo; import generated.python.contracts.presentation_plan as pp; import generated.python.contracts.slide_spec_base as ss; print('python codegen imports ok')"])
    for ts_name in ("framework_object.ts", "presentation_plan.ts", "slide_spec_base.ts"):
        ts_path = ROOT / "generated" / "typescript" / "contracts" / ts_name
        if not ts_path.is_file():
            raise SystemExit(f"TypeScript codegen did not produce {ts_name}")
    run(["npm", "run", "typecheck", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at9", "--workspace", "borek-renderer"], shell=True)
    print("typescript codegen ok")
    print("renderer contract types ok")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
