#!/usr/bin/env python3
"""Apply repository SQL migrations in order (AT-37).

Usage:
  py -3 scripts/apply_migrations.py
  py -3 scripts/apply_migrations.py --reapply

Requires DATABASE_URL or SUPABASE_DB_PASSWORD + SUPABASE_URL.
Safe to re-run: every file uses IF NOT EXISTS / DROP POLICY IF EXISTS.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "apps" / "services" / "api" / "supabase" / "migrations"

sys.path.insert(0, str(ROOT / "apps" / "services" / "api"))
from app.database_url import resolve_database_url  # noqa: E402


def migration_files() -> list[Path]:
    files = sorted(MIGRATIONS.glob("*.sql"))
    if not files:
        raise SystemExit(f"No migrations in {MIGRATIONS}")
    return files


def database_url() -> str:
    load_dotenv(ROOT / ".env")
    url = resolve_database_url(
        database_url=os.getenv("DATABASE_URL", "").strip(),
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_db_password=os.getenv("SUPABASE_DB_PASSWORD", "").strip(),
        supabase_db_pooler_host=os.getenv("SUPABASE_DB_POOLER_HOST", "").strip(),
    )
    if not url:
        raise SystemExit("Set DATABASE_URL or SUPABASE_DB_PASSWORD + SUPABASE_URL")
    return url


def apply(url: str, *, times: int = 1) -> None:
    import psycopg

    files = migration_files()
    with psycopg.connect(url, connect_timeout=20, autocommit=True) as conn:
        for attempt in range(times):
            print(f"=== apply pass {attempt + 1}/{times} ===")
            for path in files:
                sql = path.read_text(encoding="utf-8")
                print(f"Applying {path.name}")
                with conn.cursor() as cur:
                    cur.execute(sql)
    print(f"Applied {len(files)} migration file(s) {times} time(s).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Borek SQL migrations in order")
    parser.add_argument(
        "--reapply",
        action="store_true",
        help="Run the full chain twice to prove idempotency",
    )
    args = parser.parse_args()
    apply(database_url(), times=2 if args.reapply else 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
