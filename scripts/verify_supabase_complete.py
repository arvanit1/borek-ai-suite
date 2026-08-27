#!/usr/bin/env python3
"""Verify Supabase schema, RLS policies, and live isolation (AT-37 / AT-38).

Runs:
  1. scripts/verify_db.py — tables, RLS enabled, policies, auth.uid()
  2. tests/integration/api/test_rls_negative.py — user B cannot read user A data

Requires in .env (or environment):
  RUN_SUPABASE_INTEGRATION=1
  SUPABASE_URL, SUPABASE_DB_PASSWORD, SUPABASE_DB_POOLER_HOST (or remote DATABASE_URL)

Install integration deps once:
  py -3 -m pip install -e ".[dev,integration]"
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if os.getenv("RUN_SUPABASE_INTEGRATION") != "1":
        print("Set RUN_SUPABASE_INTEGRATION=1 in .env before running live Supabase verification.")
        return 1

    steps: list[tuple[str, list[str]]] = [
        ("Database schema + RLS", [sys.executable, str(ROOT / "scripts" / "verify_db.py")]),
        (
            "RLS negative integration test",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/integration/api/test_rls_negative.py",
                "-m",
                "integration",
                "-v",
            ],
        ),
    ]

    for label, command in steps:
        print(f"\n=== {label} ===", flush=True)
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode != 0:
            print(f"\nFAILED: {label}")
            return result.returncode

    print("\n=== Supabase AT-37/AT-38 verification complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
