"""AT-38: RLS negative integration test — requires live Supabase Postgres."""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.integration


def test_second_user_cannot_read_first_users_opportunity() -> None:
    if os.getenv("RUN_SUPABASE_INTEGRATION") != "1":
        pytest.skip("Set RUN_SUPABASE_INTEGRATION=1 with migrated Supabase Postgres")

    psycopg = pytest.importorskip("psycopg")

    database_url = os.environ["DATABASE_URL"]
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

            cur.execute("SET LOCAL role authenticated")
            cur.execute("SET LOCAL request.jwt.claim.sub = %s", (str(user_a),))
            cur.execute("SELECT count(*) FROM opportunities WHERE id = %s", (opportunity_id,))
            assert cur.fetchone()[0] == 1

            cur.execute("SET LOCAL request.jwt.claim.sub = %s", (str(user_b),))
            cur.execute("SELECT count(*) FROM opportunities WHERE id = %s", (opportunity_id,))
            assert cur.fetchone()[0] == 0

            cur.execute("DELETE FROM opportunities WHERE id = %s", (opportunity_id,))
