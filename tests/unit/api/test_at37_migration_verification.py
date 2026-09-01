"""AT-37: repository migrations are complete, numbered, and re-runnable."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = ROOT / "apps" / "services" / "api" / "supabase" / "migrations"
VERIFY_DB = ROOT / "scripts" / "verify_db.py"

TABLE_MIGRATIONS = [
    ("001_opportunities.sql", "opportunities"),
    ("002_transcripts.sql", "transcripts"),
    ("003_transcript_sections.sql", "transcript_sections"),
    ("004_framework_versions.sql", "framework_versions"),
    ("005_presentation_plans.sql", "presentation_plans"),
    ("006_presentations.sql", "presentations"),
    ("007_presentation_versions.sql", "presentation_versions"),
    ("008_slides.sql", "slides"),
    ("009_generation_jobs.sql", "generation_jobs"),
    ("010_audit_log.sql", "audit_log"),
]


def _sql_names() -> list[str]:
    assert MIGRATIONS_DIR.is_dir(), f"missing {MIGRATIONS_DIR}"
    return sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))


def test_all_ten_migration_files_exist() -> None:
    names = _sql_names()
    for filename, _table in TABLE_MIGRATIONS:
        assert filename in names, f"missing {filename} in {MIGRATIONS_DIR}"
    assert len(TABLE_MIGRATIONS) == 10


def test_each_file_contains_create_table_if_not_exists() -> None:
    for filename, table in TABLE_MIGRATIONS:
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        assert re.search(
            rf"CREATE TABLE IF NOT EXISTS {table}\s*\(",
            content,
        ), f"{filename} must CREATE TABLE IF NOT EXISTS {table}"


def test_each_file_contains_enable_row_level_security() -> None:
    for filename, table in TABLE_MIGRATIONS:
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        assert (
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in content
        ), f"{filename} must ENABLE ROW LEVEL SECURITY on {table}"


def test_files_numbered_001_through_011_with_no_gaps() -> None:
    numbers = sorted(
        {
            int(name.split("_", 1)[0])
            for name in _sql_names()
            if re.match(r"^\d{3}_", name)
        }
    )
    spine = [number for number in numbers if number <= 11]
    assert spine == list(range(1, 12)), f"expected 001-011 with no gaps, got {spine}"
    assert (MIGRATIONS_DIR / "011_rls_policies.sql").is_file()


def test_verify_db_script_exists_and_is_executable() -> None:
    assert VERIFY_DB.is_file(), "scripts/verify_db.py must exist"
    content = VERIFY_DB.read_text(encoding="utf-8")
    assert content.startswith("#!/usr/bin/env python3")
    if os.name == "nt":
        assert VERIFY_DB.suffix == ".py"
        compile(content, str(VERIFY_DB), "exec")
    else:
        assert os.access(VERIFY_DB, os.X_OK), f"{VERIFY_DB} must be executable"
    assert sys.executable
