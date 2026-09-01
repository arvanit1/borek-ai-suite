"""ES-32 / AT-53 — JSON-safe observability payloads for job completion."""

from __future__ import annotations

import json
import uuid

from app.services.es32_job_observability import build_framework_job_observability
from app.services.job_service import create_job
from services.knowledge_model.extraction import PROMPT_VERSION as EXTRACTION_PROMPT_VERSION
from services.observability.llm_logger import (
    STAGE_EXTRACTION,
    clear_generation_jobs,
    log_generation_job,
    log_llm_call,
    reset_llm_call_logs,
)


def test_es32_build_framework_job_observability_includes_prompt_versions() -> None:
    clear_generation_jobs()
    opportunity_id = str(uuid.uuid4())
    log_generation_job(
        stage=STAGE_EXTRACTION,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        model="claude-sonnet-4-5",
        status="success",
        attempt=1,
        opportunity_id=opportunity_id,
        input_tokens=100,
        output_tokens=200,
    )
    framework_json = {
        "generation_meta": {
            "llm_job_log": [
                {
                    "stage": "framework_synthesis",
                    "prompt_version": "framework-synthesis:v1",
                    "model": "claude-sonnet-4-5",
                    "input_tokens": 300,
                    "output_tokens": 400,
                }
            ]
        }
    }
    payload = build_framework_job_observability(
        framework_json=framework_json,
        opportunity_id=opportunity_id,
        framework_version_id=str(uuid.uuid4()),
    )
    assert EXTRACTION_PROMPT_VERSION in payload["prompt_versions"]
    assert "framework-synthesis:v1" in payload["prompt_versions"]
    assert payload["number_of_ai_calls"] >= 2
    assert payload["ai_input_tokens"] >= 400


def test_es32_job_complete_result_exposes_llm_calls() -> None:
    from app.services import framework_generation, job_service
    from app.services.data.memory_store import get_memory_store

    store = get_memory_store()
    user_id = uuid.uuid4()
    opportunity = store.create_opportunity(
        user_id=user_id,
        client_name="Acme",
        opportunity_name="Obs",
        department="Finance",
        language="en",
    )
    job = job_service.create_job(opportunity["id"], "framework_generation", repository=store)
    framework_json = {
        "generation_meta": {
            "llm_job_log": [
                {
                    "stage": "framework_synthesis",
                    "prompt_version": "framework-synthesis:v1",
                    "input_tokens": 10,
                    "output_tokens": 20,
                }
            ]
        }
    }
    framework_generation.persist_framework_generation_observability(
        job,
        framework_json=framework_json,
        opportunity_id=opportunity["id"],
        framework_version_id=uuid.uuid4(),
    )
    assert job.result_json["prompt_versions"] == ["framework-synthesis:v1"]
    assert job.number_of_ai_calls == 1


def test_at53_framework_job_observability_is_json_serializable() -> None:
    reset_llm_call_logs()
    clear_generation_jobs()
    opportunity_id = uuid.uuid4()
    job_id = uuid.uuid4()
    log_llm_call(
        request_id=uuid.uuid4(),
        stage=STAGE_EXTRACTION,
        model="claude-sonnet-4-5",
        prompt_version=EXTRACTION_PROMPT_VERSION,
        input_tokens=100,
        output_tokens=200,
        latency_ms=1500.0,
        retry_count=0,
        job_id=job_id,
        opportunity_id=opportunity_id,
    )
    payload = build_framework_job_observability(
        framework_json={"generation_meta": {}},
        opportunity_id=str(opportunity_id),
        framework_version_id=str(uuid.uuid4()),
    )
    encoded = json.dumps(payload)
    assert encoded
    at53_logs = [item for item in payload["llm_calls"] if item.get("source") == "at53"]
    assert len(at53_logs) == 1
    assert at53_logs[0]["request_id"] == str(at53_logs[0]["request_id"])
    assert isinstance(at53_logs[0]["job_id"], str)
    assert isinstance(at53_logs[0]["opportunity_id"], str)


def test_es32_merges_durable_store_llm_calls_for_job() -> None:
    from app.services.data.memory_store import get_memory_store

    reset_llm_call_logs()
    clear_generation_jobs()
    store = get_memory_store()
    job_id = uuid.uuid4()
    opportunity_id = uuid.uuid4()
    store.append_llm_call(
        {
            "request_id": str(uuid.uuid4()),
            "job_id": job_id,
            "opportunity_id": opportunity_id,
            "stage": STAGE_EXTRACTION,
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "prompt_version": EXTRACTION_PROMPT_VERSION,
            "input_tokens": 120,
            "output_tokens": 80,
            "total_tokens": 200,
            "latency_ms": 900,
            "retry_count": 0,
            "status": "success",
            "estimated_cost_eur": 0.01,
        }
    )
    payload = build_framework_job_observability(
        framework_json={"generation_meta": {}},
        opportunity_id=str(opportunity_id),
        framework_version_id=str(uuid.uuid4()),
        job_id=str(job_id),
        store=store,
    )
    assert EXTRACTION_PROMPT_VERSION in payload["prompt_versions"]
    durable = [item for item in payload["llm_calls"] if item.get("source") == "at53_durable"]
    assert len(durable) == 1
    assert durable[0]["prompt_version"] == EXTRACTION_PROMPT_VERSION
