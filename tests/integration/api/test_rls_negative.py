"""AT-38: RLS negative integration test — requires live Supabase Postgres."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "services" / "api"))

from app.database_url import LOCAL_DB_HOSTS, resolve_database_url

pytestmark = pytest.mark.integration


def _integration_database_url() -> str:
    return resolve_database_url(
        database_url=os.getenv("DATABASE_URL", "").strip(),
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_db_password=os.getenv("SUPABASE_DB_PASSWORD", "").strip(),
        supabase_db_pooler_host=os.getenv("SUPABASE_DB_POOLER_HOST", "").strip(),
    )


def _as_user(cur, user_id: uuid.UUID) -> None:
    cur.execute("SET LOCAL role authenticated")
    cur.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(user_id),))


def _count(cur, sql: str, *params) -> int:
    cur.execute(sql, params)
    row = cur.fetchone()
    assert row is not None
    return int(row[0])


def test_second_user_cannot_read_first_users_protected_rows() -> None:
    if os.getenv("RUN_SUPABASE_INTEGRATION") != "1":
        pytest.skip("Set RUN_SUPABASE_INTEGRATION=1 with migrated Supabase Postgres")

    psycopg = pytest.importorskip("psycopg")

    database_url = _integration_database_url()
    hostname = urlparse(database_url).hostname
    if not database_url or hostname in LOCAL_DB_HOSTS:
        pytest.skip(
            "Set SUPABASE_DB_PASSWORD and SUPABASE_DB_POOLER_HOST in .env "
            "(Dashboard > Connect > Connection pooling, session mode)"
        )

    user_a = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    user_b = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    opportunity_id = uuid.uuid4()
    transcript_id = uuid.uuid4()
    framework_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    presentation_id = uuid.uuid4()

    with psycopg.connect(database_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO opportunities (
                  id, client_name, opportunity_name, department, created_by
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (opportunity_id, "Client A", "Opportunity A", "Finance", user_a),
            )
            cur.execute(
                """
                INSERT INTO transcripts (
                  id, opportunity_id, file_name, mime_type, storage_path, conversation_id
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    transcript_id,
                    opportunity_id,
                    "call.txt",
                    "text/plain",
                    f"{opportunity_id}/call.txt",
                    "C-AT38",
                ),
            )
            cur.execute(
                """
                INSERT INTO framework_versions (
                  id, opportunity_id, version_number, status, framework_json, created_by
                ) VALUES (%s, %s, 1, 'confirmed', '{}'::jsonb, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (framework_id, opportunity_id, user_a),
            )
            cur.execute(
                """
                INSERT INTO presentation_plans (
                  id, framework_version_id, plan_json
                ) VALUES (%s, %s, '{}'::jsonb)
                ON CONFLICT (id) DO NOTHING
                """,
                (plan_id, framework_id),
            )
            cur.execute(
                """
                INSERT INTO presentations (
                  id, presentation_plan_id, name, status
                ) VALUES (%s, %s, %s, 'draft')
                ON CONFLICT (id) DO NOTHING
                """,
                (presentation_id, plan_id, "AT-38 Deck"),
            )

        checks = (
            ("opportunities", "SELECT count(*) FROM opportunities WHERE id = %s", opportunity_id),
            ("transcripts", "SELECT count(*) FROM transcripts WHERE id = %s", transcript_id),
            (
                "framework_versions",
                "SELECT count(*) FROM framework_versions WHERE id = %s",
                framework_id,
            ),
            (
                "presentations",
                "SELECT count(*) FROM presentations WHERE id = %s",
                presentation_id,
            ),
        )
        for label, sql, row_id in checks:
            with conn.transaction():
                with conn.cursor() as cur:
                    _as_user(cur, user_a)
                    assert _count(cur, sql, row_id) == 1, f"user A should see {label}"
            with conn.transaction():
                with conn.cursor() as cur:
                    _as_user(cur, user_b)
                    assert _count(cur, sql, row_id) == 0, f"user B must not see {label}"

        with conn.cursor() as cur:
            cur.execute("DELETE FROM opportunities WHERE id = %s", (opportunity_id,))
