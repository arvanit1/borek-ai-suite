"""MS-30 live Supabase proof; opt in with RUN_SUPABASE_INTEGRATION=1."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.auth import decode_access_token
from app.config import settings
from app.services.data.supabase_store import SupabaseDataStore
from app.services.demo_data import SupabaseDemoRecordStore, install_demo_data

pytestmark = pytest.mark.integration


def test_demo_pack_is_idempotent_and_hidden_from_second_user(
    _rls_access_tokens: dict[str, str],
    client_user_a,
    client_user_b,
) -> None:
    token_a = _rls_access_tokens["a"]
    token_b = _rls_access_tokens["b"]
    user_a = decode_access_token(token_a)
    configured_root = Path(settings.ARTIFACT_ROOT)
    artifact_root = configured_root if configured_root.is_absolute() else Path.cwd() / configured_root
    store = SupabaseDemoRecordStore(
        base_url=settings.SUPABASE_URL,
        service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    )

    first = install_demo_data(user_id=user_a.id, store=store, artifact_root=artifact_root)
    second = install_demo_data(user_id=user_a.id, store=store, artifact_root=artifact_root)
    assert first == second

    owned = client_user_a.get(f"/opportunities/{first.rich_opportunity_id}")
    hidden = client_user_b.get(f"/opportunities/{first.rich_opportunity_id}")
    assert owned.status_code == 200, owned.text
    assert owned.json()["demo_marker"] == "demo"
    assert hidden.status_code in {403, 404}

    filed = client_user_a.get(f"/opportunities/{first.rich_opportunity_id}/filed-artifacts")
    hidden_filed = client_user_b.get(
        f"/opportunities/{first.rich_opportunity_id}/filed-artifacts"
    )
    assert filed.status_code == 200, filed.text
    assert len(filed.json()) == 6
    assert all(row["demo_marker"] == "demo" for row in filed.json())
    assert hidden_filed.status_code in {403, 404}

    archive_a = client_user_a.get("/archive/artifacts?search=Northstar")
    archive_b = client_user_b.get("/archive/artifacts?search=Northstar")
    assert archive_a.status_code == 200, archive_a.text
    assert len(archive_a.json()) == 6
    assert archive_b.status_code == 200
    assert archive_b.json() == []
    download = client_user_a.get(archive_a.json()[0]["download_url"])
    denied_download = client_user_b.get(archive_a.json()[0]["download_url"])
    assert download.status_code == 200
    assert denied_download.status_code == 404

    facts_a = SupabaseDataStore(token_a).list_approved_knowledge_facts()
    facts_b = SupabaseDataStore(token_b).list_approved_knowledge_facts()
    assert any(row["corpus_key"] == "borek-demo" for row in facts_a)
    assert not any(row["corpus_key"] == "borek-demo" for row in facts_b)
