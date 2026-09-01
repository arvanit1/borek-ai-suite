#!/usr/bin/env python3
"""Optional integration gate — requires Redis and other external services.

AT-38 live RLS isolation (tests/integration/api/test_at38_rls_isolation.py)
runs only when RUN_SUPABASE_INTEGRATION=1 and the RLS_TEST_USER_* credentials
are present. The main client-delivery gate (validate_all.py) does not set that
flag.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AT38_PATH = "tests/integration/api/test_at38_rls_isolation.py"


def main() -> int:
    print("+ pytest tests/integration -m integration --ignore AT-38 -v")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration",
            "-m",
            "integration",
            f"--ignore={AT38_PATH}",
            "-v",
        ],
        cwd=ROOT,
        check=True,
    )

    if os.getenv("RUN_SUPABASE_INTEGRATION") == "1":
        print(f"+ pytest {AT38_PATH} -v")
        subprocess.run(
            [sys.executable, "-m", "pytest", AT38_PATH, "-v"],
            cwd=ROOT,
            check=True,
        )
    else:
        print("SKIP AT-38 live RLS isolation (RUN_SUPABASE_INTEGRATION != 1)")

    print("ALL INTEGRATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
