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


def test_stage_a_wiring_migration_adds_private_transcript_storage() -> None:
    path = MIGRATIONS_DIR / "012_transcript_content_storage.sql"
    content = path.read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS conversation_id TEXT" in content
    assert "storage.buckets" in content
    assert "VALUES ('transcripts', 'transcripts', false)" in content
    assert "users_own_transcript_objects" in content
    assert "created_by = auth.uid()" in content


def test_generation_job_runtime_migration_adds_results_and_metrics() -> None:
    content = (
        MIGRATIONS_DIR / "013_generation_job_runtime_fields.sql"
    ).read_text(encoding="utf-8")
    for column in (
        "failed_stage",
        "error_retryable",
        "result_json",
        "ai_input_tokens",
        "ai_output_tokens",
        "number_of_ai_calls",
        "render_duration_ms",
        "storage_size_bytes",
        "generation_cost_estimate",
        "created_at",
    ):
        assert f"ADD COLUMN IF NOT EXISTS {column}" in content


def test_llm_calls_migration_creates_durable_observability_table() -> None:
    content = (MIGRATIONS_DIR / "014_llm_calls.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS llm_calls" in content
    assert "ALTER TABLE llm_calls ENABLE ROW LEVEL SECURITY;" in content
    assert "users_own_llm_calls" in content
    assert "ADD COLUMN IF NOT EXISTS llm_cost_eur" in content
    assert "created_by = auth.uid()" in content
