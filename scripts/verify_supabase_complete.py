#!/usr/bin/env python3
"""Verify Supabase schema, migrations, RLS policies, and live isolation (AT-37 / AT-38 / AT-53).

Runs:
  1. scripts/apply_migrations.py --reapply — idempotent migration chain
  2. scripts/verify_db.py — tables, RLS enabled, policies, auth.uid()
  3. tests/integration/api/test_at37_apply_migrations.py — hosted reapply proof
  4. tests/integration/api/test_rls_negative.py — direct Postgres RLS rejection
  5. tests/integration/api/test_at38_rls_isolation.py — HTTP cross-user isolation
  6. tests/integration/api/test_at53_llm_calls_persist.py — durable llm_calls rows

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
        (
            "Apply migrations (idempotent reapply)",
            [sys.executable, str(ROOT / "scripts" / "apply_migrations.py"), "--reapply"],
        ),
        ("Database schema + RLS", [sys.executable, str(ROOT / "scripts" / "verify_db.py")]),
        (
            "AT-37 hosted migration reapply",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/integration/api/test_at37_apply_migrations.py",
                "-v",
            ],
        ),
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
        (
            "AT-38 HTTP RLS isolation (two real users)",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/integration/api/test_at38_rls_isolation.py",
                "-v",
            ],
        ),
        (
            "AT-53 durable llm_calls persistence",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/integration/api/test_at53_llm_calls_persist.py",
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

    print("\n=== Supabase AT-37/AT-38/AT-53 verification complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
