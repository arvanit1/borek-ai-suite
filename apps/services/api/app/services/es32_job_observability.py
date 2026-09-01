"""ES-32 — persist ES prompt-version records on production generation jobs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from services.observability.llm_logger import get_llm_call_logs, jobs_for_opportunity


def build_framework_job_observability(
    *,
    framework_json: dict[str, Any],
    opportunity_id: str,
    framework_version_id: str,
) -> dict[str, Any]:
    """Merge ES-32 generation logs and AT-53 call metadata for durable job results."""
    generation_meta = framework_json.get("generation_meta") or {}
    es_logs = list(generation_meta.get("llm_job_log") or [])
    es_opportunity_jobs = [
        {**item, "source": "es32"}
        for item in jobs_for_opportunity(opportunity_id)
    ]
    at53_logs = [
        {
            **asdict(entry),
            "timestamp": entry.timestamp.isoformat().replace("+00:00", "Z"),
            "source": "at53",
        }
        for entry in get_llm_call_logs()
    ]
    llm_calls = [*es_logs, *es_opportunity_jobs, *at53_logs]
    prompt_versions = sorted(
        {
            str(item.get("prompt_version") or "")
            for item in llm_calls
            if item.get("prompt_version")
        }
    )
    input_tokens = sum(int(item.get("input_tokens") or 0) for item in llm_calls)
    output_tokens = sum(int(item.get("output_tokens") or 0) for item in llm_calls)
    return {
        "framework_version_id": framework_version_id,
        "opportunity_id": opportunity_id,
        "llm_calls": llm_calls,
        "prompt_versions": prompt_versions,
        "prompt_observability": generation_meta.get("prompt_observability") or {},
        "ai_input_tokens": input_tokens,
        "ai_output_tokens": output_tokens,
        "number_of_ai_calls": len(llm_calls),
    }


def apply_framework_job_observability(job: Any, payload: dict[str, Any]) -> None:
    job.result_json = dict(payload)
    job.ai_input_tokens = int(payload.get("ai_input_tokens") or 0)
    job.ai_output_tokens = int(payload.get("ai_output_tokens") or 0)
    job.number_of_ai_calls = int(payload.get("number_of_ai_calls") or 0)
