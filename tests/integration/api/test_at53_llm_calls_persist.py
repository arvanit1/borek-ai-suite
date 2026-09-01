"""AT-53: durable llm_calls rows survive on hosted Supabase."""

from __future__ import annotations

import os
import uuid

import pytest

from llm.client import LlmClient
from services.observability.llm_logger import (
    LlmStage,
    invoke_llm,
    llm_observability_scope,
    reset_llm_call_logs,
)
from services.slides.content_generation.group_a.common import StructuredGenerationRequest

pytestmark = pytest.mark.integration


def _skip_unless_live() -> None:
    if os.getenv("RUN_SUPABASE_INTEGRATION") != "1":
        pytest.skip("Set RUN_SUPABASE_INTEGRATION=1 to persist llm_calls on hosted Supabase")


def test_hosted_llm_calls_survive_for_a_real_job(
    client_user_a, _rls_access_tokens
) -> None:
    _skip_unless_live()
    from uuid import UUID

    from app.auth import decode_access_token
    from app.services import job_service
    from app.services.data.supabase_store import SupabaseDataStore
    from app.schemas.jobs import JobStage

    created = client_user_a.post(
        "/opportunities",
        json={
            "client_name": "AT-53 Client",
            "opportunity_name": "AT-53 Durable Observability",
            "department": "Finance",
        },
    )
    assert created.status_code == 201, created.text
    opportunity_id = UUID(created.json()["id"])
    user = decode_access_token(_rls_access_tokens["a"])
    store = SupabaseDataStore(_rls_access_tokens["a"])
    job = job_service.create_job(
        opportunity_id,
        "framework_generation",
        repository=store,
    )
    job_service.advance_stage(
        job.id,
        JobStage.FRAMEWORK_SYNTHESIZING,
        repository=store,
    )
    reset_llm_call_logs()
    with llm_observability_scope(
        job_id=job.id,
        opportunity_id=opportunity_id,
        store=store,
    ):
        client = LlmClient()
        client.complete_framework(prompt_version="synthesis_v1", retry_count=0)
        client.complete_planning(prompt_version="presentation_planner_v1", retry_count=1)
        client.structured_generator(prompt_version="context_01_v1", retry_count=0)(
            StructuredGenerationRequest(
                layout_id="CONTEXT_01",
                chapters=({"chapter_id": "1", "title": "Context", "body": []},),
                target_schema={"type": "object"},
                instructions="Grounded only.",
            )
        )
        client.compression_fields_fn(prompt_version="compression_v1", retry_count=2)(
            {"title": "A very long title that exceeds limits"},
            [],
        )
        invoke_llm(
            stage=LlmStage.FRAMEWORK,
            model="claude-sonnet-4",
            prompt_version="synthesis_v1",
            retry_count=0,
            call=lambda: {"ok": True},
            input_tokens=lambda _: 40,
            output_tokens=lambda _: 20,
        )

    rows = store.get_llm_calls_for_job(str(job.id))
    stages = {row["stage"] for row in rows}
    assert {"framework", "planning", "slide_generation", "compression"} <= stages
    assert all("prompt" not in row and "messages" not in row for row in rows)
    assert any(int(row.get("retry_count") or 0) >= 2 for row in rows)
    completed = job_service.complete_job(job.id, repository=store)
    assert completed.number_of_ai_calls >= 4
    assert completed.ai_input_tokens > 0
    assert completed.llm_cost_eur >= 0
