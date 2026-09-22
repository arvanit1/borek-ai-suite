"""BT-34 authenticated intake -> store -> research + existing prompt orchestration.

Fixture-backed; no provider, database, renderer or LLM network calls.
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.services.data.memory_store import get_memory_store
from app.services.stage_a_orchestration import generate_framework_from_transcripts
from services.framework.synthesis import _user_prompt
from services.framework.stage1_research import validate_research
from services.knowledge_model.extraction import _format_user_message

OWNER = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def test_intake_research_and_existing_framework_context_are_connected():
    token = create_test_access_token(
        user_id=OWNER, email="sales@example.com", secret=settings.SUPABASE_JWT_SECRET
    )
    headers = {"Authorization": f"Bearer {token}"}
    app = create_app()
    with TestClient(app) as client:
        created = client.post(
            "/opportunities",
            headers=headers,
            json={
                "client_name": "Acme",
                "opportunity_name": "Invoice matching",
                "department": "Finance",
                "stage1_intake": {
                    "sales_topic_description": "Explore invoice matching",
                    "about_company": "Sales description",
                },
            },
        )
        assert created.status_code == 201
        opportunity_id = created.json()["id"]

    # A new request client retrieves persisted intake without a meeting upload.
    with TestClient(app) as client:
        path = f"/opportunities/{opportunity_id}"
        saved = client.get(path, headers=headers).json()
        assert saved["stage1_intake"]["about_company"] == "Sales description"
        response = client.post(path + "/stage1-research", headers=headers)
        assert response.status_code == 200
        research = response.json()
        validate_research(research)
        assert research["company_facts"]["revenue"]["status"] == "unknown"
        assert (
            research["user_statements"]["fields"]["about_company"]
            == "Sales description"
        )

    # Compatibility check only: the existing transcript path still passes the
    # persisted sales context to its extraction and synthesis builders. BT-35
    # will provide the separate document-driven First Contact entrypoint.
    store = get_memory_store()
    opp_id = UUID(opportunity_id)
    store.create_transcript(
        opportunity_id=opp_id,
        user_id=OWNER,
        file_name="meeting.txt",
        mime_type="text/plain",
        storage_path=f"{opp_id}/meeting.txt",
        conversation_id="C1",
        content=b"Rep: Invoice matching",
        sections=[
            {
                "section_index": 0,
                "speaker_role": "Rep",
                "content": "Invoice matching",
                "metadata": {"conversation_id": "C1"},
            }
        ],
    )
    prompts = {}

    def extract(turns, identity, **kwargs):
        prompts["extraction"] = _format_user_message(
            turns, identity, stage1_intake=kwargs["stage1_intake"]
        )
        return {"facts": [], "conversation_id": "C1"}

    def generate(models, **kwargs):
        prompts["synthesis"] = _user_prompt(
            {}, {}, stage1_intake=kwargs["stage1_intake"]
        )
        return {
            "title": "Fixture",
            "chapters": [],
            "open_items": [],
            "generation_meta": {},
        }

    generate_framework_from_transcripts(
        store,
        opportunity_id=opp_id,
        user_id=OWNER,
        execution_mode="live",
        extract_fn=extract,
        generate_fn=generate,
    )
    for prompt in prompts.values():
        assert "STAGE1_INTAKE_BEGIN" in prompt
        assert "Sales description" in prompt
        assert '"origin": "USER_INPUT"' in prompt
    assert "voice_transcript" not in json.dumps(prompts)
