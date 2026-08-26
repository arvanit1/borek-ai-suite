#!/usr/bin/env python3
"""Optional integration gate — requires Redis and other external services."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print("+ pytest tests/integration -m integration -v")
    subprocess.run(
        [sys.executable, "-m", "pytest", "tests/integration", "-m", "integration", "-v"],
        cwd=ROOT,
        check=True,
    )
    print("ALL INTEGRATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
