"""Stage 3: job-scoped prompt versions and cost survive an in-memory logger reset."""

from __future__ import annotations

import uuid

from app.schemas.jobs import JobStage
from app.services import framework_generation, job_service
from app.services.data.memory_store import get_memory_store
from services.knowledge_model.extraction import PROMPT_VERSION as EXTRACTION_PROMPT_VERSION
from services.observability.llm_logger import (
    STAGE_EXTRACTION,
    clear_generation_jobs,
    reset_llm_call_logs,
)


def test_observability_survives_process_memory_wipe() -> None:
    store = get_memory_store()
    user_id = uuid.uuid4()
    opportunity = store.create_opportunity(
        user_id=user_id,
        client_name="Acme",
        opportunity_name="Obs restart",
        department="Finance",
        language="en",
    )
    job = job_service.create_job(opportunity["id"], "framework_generation", repository=store)
    job_service.ensure_stage(job.id, JobStage.FRAMEWORK_VALIDATING, repository=store)
    store.append_llm_call(
        {
            "request_id": str(uuid.uuid4()),
            "job_id": job.id,
            "opportunity_id": opportunity["id"],
            "stage": STAGE_EXTRACTION,
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "prompt_version": EXTRACTION_PROMPT_VERSION,
            "input_tokens": 120,
            "output_tokens": 80,
            "total_tokens": 200,
            "latency_ms": 900,
            "retry_count": 1,
            "status": "success",
            "estimated_cost_eur": 0.02,
        }
    )
    payload = framework_generation.persist_framework_generation_observability(
        job,
        framework_json={
            "generation_meta": {
                "llm_job_log": [
                    {
                        "stage": "framework_synthesis",
                        "prompt_version": "framework-synthesis:v2",
                        "input_tokens": 300,
                        "output_tokens": 400,
                    }
                ]
            }
        },
        opportunity_id=opportunity["id"],
        framework_version_id=uuid.uuid4(),
        repository=store,
    )
    job_service.complete_job(job.id, repository=store, result_json=payload)

    reset_llm_call_logs()
    clear_generation_jobs()

    restored = job_service.get_job(job.id, repository=store)
    assert restored is not None
    assert EXTRACTION_PROMPT_VERSION in restored.result_json["prompt_versions"]
    assert "framework-synthesis:v2" in restored.result_json["prompt_versions"]
    assert restored.result_json["number_of_ai_calls"] >= 2
    assert restored.result_json["ai_input_tokens"] >= 420
    durable = [item for item in restored.result_json["llm_calls"] if item.get("source") == "at53_durable"]
    assert durable
    assert durable[0]["retry_count"] == 1
    assert durable[0]["estimated_cost_eur"] == 0.02
