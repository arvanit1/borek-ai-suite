"""Service-role presentation reads must preserve user ownership boundaries."""

from __future__ import annotations

from datetime import UTC, datetime
from types import MethodType
from uuid import UUID

import httpx

from app.services.data.supabase_store import SupabaseDataStore


USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
OPPORTUNITY_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
FRAMEWORK_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
PLAN_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
PRESENTATION_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")


def _opportunity_row() -> dict[str, str]:
    timestamp = datetime(2026, 9, 14, tzinfo=UTC).isoformat()
    return {
        "id": str(OPPORTUNITY_ID),
        "created_by": str(USER_ID),
        "client_name": "Acme",
        "opportunity_name": "Scoped presentation lookup",
        "department": "Finance",
        "language": "en",
        "status": "active",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def test_list_presentations_for_opportunity_scopes_service_role_reads() -> None:
    store = SupabaseDataStore.__new__(SupabaseDataStore)
    requests: list[tuple[str, dict[str, str]]] = []

    def fake_request(
        _store: SupabaseDataStore,
        _method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        json_body=None,
    ) -> httpx.Response:
        assert json_body is None
        request_params = params or {}
        requests.append((table, request_params))
        if table == "opportunities":
            return httpx.Response(200, json=[_opportunity_row()])
        if table == "framework_versions":
            return httpx.Response(200, json=[{"id": str(FRAMEWORK_ID)}])
        if table == "presentation_plans":
            return httpx.Response(200, json=[{"id": str(PLAN_ID)}])
        if table == "presentations":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(PRESENTATION_ID),
                        "presentation_plan_id": str(PLAN_ID),
                        "name": "Owned presentation",
                        "created_at": datetime(2026, 9, 14, tzinfo=UTC).isoformat(),
                    }
                ],
            )
        raise AssertionError(f"Unexpected table: {table}")

    store._request = MethodType(fake_request, store)

    rows = store.list_presentations_for_opportunity(
        opportunity_id=OPPORTUNITY_ID,
        user_id=USER_ID,
    )

    assert [row["id"] for row in rows] == [PRESENTATION_ID]
    assert requests == [
        (
            "opportunities",
            {
                "select": "*",
                "id": f"eq.{OPPORTUNITY_ID}",
                "created_by": f"eq.{USER_ID}",
                "limit": "1",
            },
        ),
        (
            "framework_versions",
            {
                "select": "id",
                "opportunity_id": f"eq.{OPPORTUNITY_ID}",
                "created_by": f"eq.{USER_ID}",
            },
        ),
        (
            "presentation_plans",
            {
                "select": "id",
                "framework_version_id": f"in.({FRAMEWORK_ID})",
            },
        ),
        (
            "presentations",
            {
                "select": "*",
                "presentation_plan_id": f"in.({PLAN_ID})",
                "order": "created_at.desc",
            },
        ),
    ]


def test_list_presentations_stops_when_owned_opportunity_has_no_frameworks() -> None:
    store = SupabaseDataStore.__new__(SupabaseDataStore)
    requested_tables: list[str] = []

    def fake_request(
        _store: SupabaseDataStore,
        _method: str,
        table: str,
        *,
        params=None,
        json_body=None,
    ) -> httpx.Response:
        requested_tables.append(table)
        if table == "opportunities":
            return httpx.Response(200, json=[_opportunity_row()])
        if table == "framework_versions":
            return httpx.Response(200, json=[])
        raise AssertionError(f"Unexpected unscoped read from {table}")

    store._request = MethodType(fake_request, store)

    assert (
        store.list_presentations_for_opportunity(
            opportunity_id=OPPORTUNITY_ID,
            user_id=USER_ID,
        )
        == []
    )
    assert requested_tables == ["opportunities", "framework_versions"]
