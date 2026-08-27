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


def _count_visible_opportunity(cur, *, user_id: uuid.UUID, opportunity_id: uuid.UUID) -> int:
    """Query as authenticated role with a simulated JWT sub claim."""
    cur.execute("SET LOCAL role authenticated")
    cur.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(user_id),))
    cur.execute("SELECT count(*) FROM opportunities WHERE id = %s", (opportunity_id,))
    row = cur.fetchone()
    assert row is not None
    return int(row[0])


def test_second_user_cannot_read_first_users_opportunity() -> None:
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

        # SET LOCAL only applies inside a transaction — required for auth.uid() simulation.
        with conn.transaction():
            with conn.cursor() as cur:
                assert _count_visible_opportunity(cur, user_id=user_a, opportunity_id=opportunity_id) == 1

        with conn.transaction():
            with conn.cursor() as cur:
                assert _count_visible_opportunity(cur, user_id=user_b, opportunity_id=opportunity_id) == 0

        with conn.cursor() as cur:
            cur.execute("DELETE FROM opportunities WHERE id = %s", (opportunity_id,))
