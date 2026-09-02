"""ES-32 — persist ES prompt-version records on production generation jobs."""

from __future__ import annotations

import json
from typing import Any

from services.observability.llm_logger import get_llm_call_logs, jobs_for_opportunity


def _normalize_durable_call(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": str(row.get("request_id") or ""),
        "stage": str(row.get("stage") or ""),
        "model": str(row.get("model") or ""),
        "prompt_version": str(row.get("prompt_version") or ""),
        "input_tokens": int(row.get("input_tokens") or 0),
        "output_tokens": int(row.get("output_tokens") or 0),
        "total_tokens": int(row.get("total_tokens") or 0),
        "latency_ms": float(row.get("latency_ms") or 0),
        "retry_count": int(row.get("retry_count") or 0),
        "timestamp": str(row.get("created_at") or row.get("timestamp") or ""),
        "job_id": str(row.get("job_id") or "") or None,
        "opportunity_id": str(row.get("opportunity_id") or "") or None,
        "provider": str(row.get("provider") or "unknown"),
        "status": str(row.get("status") or "success"),
        "error_category": row.get("error_category"),
        "estimated_cost_eur": float(row.get("estimated_cost_eur") or 0),
        "source": "at53_durable",
    }


def _merge_llm_calls(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            request_id = str(item.get("request_id") or "")
            key = request_id or f"{item.get('stage')}:{item.get('prompt_version')}:{len(merged)}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def build_framework_job_observability(
    *,
    framework_json: dict[str, Any],
    opportunity_id: str,
    framework_version_id: str,
    job_id: str | None = None,
    store: Any | None = None,
) -> dict[str, Any]:
    """Merge ES-32 generation logs and AT-53 call metadata for durable job results."""
    generation_meta = framework_json.get("generation_meta") or {}
    es_logs = list(generation_meta.get("llm_job_log") or [])
    es_opportunity_jobs = [
        {**item, "source": "es32"}
        for item in jobs_for_opportunity(opportunity_id)
    ]
    at53_logs = [
        {**entry.to_json_dict(), "source": "at53"}
        for entry in get_llm_call_logs()
        if entry.opportunity_id is not None
        and str(entry.opportunity_id) == str(opportunity_id)
    ]
    durable_logs: list[dict[str, Any]] = []
    if job_id and store is not None:
        getter = getattr(store, "get_llm_calls_for_job", None)
        if getter is not None:
            durable_logs = [_normalize_durable_call(row) for row in getter(str(job_id))]
    llm_calls = _merge_llm_calls(es_logs, es_opportunity_jobs, at53_logs, durable_logs)
    prompt_versions = sorted(
        {
            str(item.get("prompt_version") or "")
            for item in llm_calls
            if item.get("prompt_version")
        }
    )
    input_tokens = sum(int(item.get("input_tokens") or 0) for item in llm_calls)
    output_tokens = sum(int(item.get("output_tokens") or 0) for item in llm_calls)
    payload = {
        "framework_version_id": framework_version_id,
        "opportunity_id": opportunity_id,
        "llm_calls": llm_calls,
        "prompt_versions": prompt_versions,
        "prompt_observability": generation_meta.get("prompt_observability") or {},
        "ai_input_tokens": input_tokens,
        "ai_output_tokens": output_tokens,
        "number_of_ai_calls": len(llm_calls),
    }
    # AT-53: job completion must survive Supabase JSON encoding.
    json.dumps(payload)
    return payload


def apply_framework_job_observability(job: Any, payload: dict[str, Any]) -> None:
    job.result_json = dict(payload)
    job.ai_input_tokens = int(payload.get("ai_input_tokens") or 0)
    job.ai_output_tokens = int(payload.get("ai_output_tokens") or 0)
    job.number_of_ai_calls = int(payload.get("number_of_ai_calls") or 0)
