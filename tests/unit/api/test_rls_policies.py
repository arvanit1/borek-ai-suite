"""AT-38: RLS policy migration file content tests."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = ROOT / "apps" / "services" / "api" / "supabase" / "migrations" / "011_rls_policies.sql"

TABLES = [
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

UUID_LITERAL = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def test_rls_migration_file_exists() -> None:
    assert MIGRATION_PATH.is_file()


def test_rls_migration_has_policy_for_each_table() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    for table in TABLES:
        assert re.search(rf'CREATE POLICY "[^"]+"\s*\n\s*ON {table}\b', content)


def test_all_policies_reference_auth_uid() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    policy_blocks = re.findall(
        r'CREATE POLICY "[^"]+"[\s\S]*?USING \([\s\S]*?\);',
        content,
    )
    assert len(policy_blocks) == len(TABLES)
    for block in policy_blocks:
        assert "auth.uid()" in block


def test_no_hardcoded_uuid_literals_in_policies() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert UUID_LITERAL.search(content) is None


def test_audit_log_policy_uses_actor_id() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    audit_block = re.search(
        r'CREATE POLICY "users_own_audit_entries"[\s\S]*?USING \(actor_id = auth\.uid\(\)\);',
        content,
    )
    assert audit_block is not None
    assert "opportunity_id" not in audit_block.group(0)


def test_opportunities_policy_uses_created_by() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'CREATE POLICY "users_own_opportunities"' in content
    assert "created_by = auth.uid()" in content


def test_opportunity_scoped_tables_use_subquery_pattern() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    subquery_tables = [
        "transcripts",
        "framework_versions",
        "generation_jobs",
    ]
    for table in subquery_tables:
        block = re.search(
            rf'CREATE POLICY "[^"]+"\s*\n\s*ON {table}[\s\S]*?USING \([\s\S]*?\);',
            content,
        )
        assert block is not None
        assert "SELECT id FROM opportunities" in block.group(0)
        assert "created_by = auth.uid()" in block.group(0)
