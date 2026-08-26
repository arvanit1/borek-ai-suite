"""AT-37: Supabase migration file content tests."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = ROOT / "apps" / "services" / "api" / "supabase" / "migrations"

EXPECTED_FILES = [
    "001_opportunities.sql",
    "002_transcripts.sql",
    "003_transcript_sections.sql",
    "004_framework_versions.sql",
    "005_presentation_plans.sql",
    "006_presentations.sql",
    "007_presentation_versions.sql",
    "008_slides.sql",
    "009_generation_jobs.sql",
    "010_audit_log.sql",
]

EXPECTED_TABLES = [
    "opportunities",
    "transcripts",
    "transcript_sections",
    "framework_versions",
    "presentation_plans",
    "presentations",
    "presentation_versions",
    "slides",
    "generation_jobs",
    "audit_log",
]

FK_EXPECTATIONS = {
    "002_transcripts.sql": "REFERENCES opportunities(id)",
    "003_transcript_sections.sql": "REFERENCES transcripts(id)",
    "004_framework_versions.sql": "REFERENCES opportunities(id)",
    "005_presentation_plans.sql": "REFERENCES framework_versions(id)",
    "006_presentations.sql": "REFERENCES presentation_plans(id)",
    "007_presentation_versions.sql": "REFERENCES presentations(id)",
    "008_slides.sql": "REFERENCES presentation_versions(id)",
    "009_generation_jobs.sql": "REFERENCES opportunities(id)",
}


def test_all_ten_migration_files_exist() -> None:
    assert MIGRATIONS_DIR.is_dir()
    files = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    for expected in EXPECTED_FILES:
        assert expected in files
    assert len([name for name in files if name.startswith(("001_", "002_", "003_", "004_", "005_", "006_", "007_", "008_", "009_", "010_"))]) == 10


def test_migration_files_numbered_001_through_010() -> None:
    numbers = [int(name.split("_", 1)[0]) for name in EXPECTED_FILES]
    assert numbers == list(range(1, 11))


def test_each_migration_creates_table_with_if_not_exists() -> None:
    for filename, table in zip(EXPECTED_FILES, EXPECTED_TABLES, strict=True):
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        assert re.search(rf"CREATE TABLE IF NOT EXISTS {table}\s*\(", content)


def test_each_migration_enables_row_level_security() -> None:
    for filename, table in zip(EXPECTED_FILES, EXPECTED_TABLES, strict=True):
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in content


def test_foreign_key_references_are_consistent() -> None:
    for filename, fk_snippet in FK_EXPECTATIONS.items():
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        assert fk_snippet in content


def test_migrations_contain_no_application_logic() -> None:
    forbidden = re.compile(
        r"^\s*(INSERT|UPDATE|DELETE|CREATE FUNCTION|CREATE TRIGGER)\b",
        re.IGNORECASE | re.MULTILINE,
    )
    for filename in EXPECTED_FILES:
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        assert forbidden.search(content) is None
