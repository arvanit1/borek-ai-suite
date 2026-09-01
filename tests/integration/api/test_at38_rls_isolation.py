"""AT-38: live RLS tenant isolation with two real Supabase Auth users."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def _skip_unless_live() -> None:
    if os.getenv("RUN_SUPABASE_INTEGRATION") != "1":
        pytest.skip("Set RUN_SUPABASE_INTEGRATION=1 to run live RLS isolation tests")


@pytest.mark.integration
class TestRLSIsolation:
    def test_user_b_cannot_read_user_a_opportunity(
        self, client_user_a, client_user_b
    ):
        _skip_unless_live()
        resp = client_user_a.post(
            "/opportunities",
            json={
                "client_name": "AT-38 Client A",
                "opportunity_name": "AT-38 Isolated Opportunity",
                "department": "Finance",
            },
        )
        assert resp.status_code == 201, resp.text
        opp_id = resp.json()["id"]

        assert client_user_a.get(f"/opportunities/{opp_id}").status_code == 200
        assert client_user_b.get(f"/opportunities/{opp_id}").status_code in (403, 404)

    def test_user_b_cannot_read_user_a_framework(
        self, client_user_a, client_user_b, confirmed_framework_id
    ):
        _skip_unless_live()
        assert client_user_a.get(
            f"/frameworks/{confirmed_framework_id}"
        ).status_code == 200
        assert client_user_b.get(
            f"/frameworks/{confirmed_framework_id}"
        ).status_code in (403, 404)

    def test_user_b_cannot_list_user_a_opportunities(
        self, client_user_a, client_user_b
    ):
        _skip_unless_live()
        created = client_user_a.post(
            "/opportunities",
            json={
                "client_name": "AT-38 Client A",
                "opportunity_name": "AT-38 Hidden From List",
                "department": "Finance",
            },
        )
        assert created.status_code == 201, created.text
        resp = client_user_b.get("/opportunities")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_b_cannot_read_user_a_transcripts(
        self, client_user_a, client_user_b, opportunity_with_transcript
    ):
        _skip_unless_live()
        opp_id, transcript_id = opportunity_with_transcript
        listed = client_user_a.get(f"/opportunities/{opp_id}/transcripts")
        assert listed.status_code == 200
        assert any(row["id"] == transcript_id for row in listed.json())
        assert client_user_b.get(
            f"/opportunities/{opp_id}/transcripts"
        ).status_code in (403, 404)
