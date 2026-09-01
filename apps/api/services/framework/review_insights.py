"""ES-36/ES-37 — structured framework review summary and attention signals."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from services.framework.chapter_validators.base import ChapterValidationError, chapter_by_id
from services.framework.customer_view import resolve_customer_view
from services.framework.pre_confirm_check import PreConfirmError, pre_confirm_check

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PII_CONFIG_PATH = _REPO_ROOT / "config" / "pii_redaction.yaml"

REVIEW_STATE_READY = "READY_TO_APPROVE"
REVIEW_STATE_RECOMMENDED = "REVIEW_RECOMMENDED"
REVIEW_STATE_BLOCKING = "BLOCKING_CONTRADICTION"
REVIEW_STATE_MISSING = "MISSING_REQUIRED_INFORMATION"
REVIEW_STATE_WEAK_EVIDENCE = "WEAK_EVIDENCE"


def attach_review_insights(
    framework: dict[str, Any],
    *,
    pii_redaction_enabled: bool | None = None,
) -> dict[str, Any]:
    """Attach ES-36 review_summary, ES-37 attention bundle, and observability metadata."""
    generation_meta = dict(framework.get("generation_meta") or {})
    generation_meta["pii_handling"] = build_pii_handling_meta(
        redaction_enabled=pii_redaction_enabled,
    )
    generation_meta["prompt_observability"] = build_prompt_observability(generation_meta)
    framework["generation_meta"] = generation_meta
    framework["review_summary"] = build_review_summary(framework)
    framework["attention"] = build_attention_bundle(framework)
    framework["attention_signals"] = framework["attention"]["signals"]
    return framework


def build_pii_handling_meta(*, redaction_enabled: bool | None = None) -> dict[str, Any]:
    cfg = _load_pii_config()
    enabled = cfg.get("default_enabled", True) if redaction_enabled is None else redaction_enabled
    redact = cfg.get("redact") or {}
    return {
        "redaction_enabled": bool(enabled),
        "applied_before_llm": bool(enabled),
        "policy_path": "config/pii_redaction.yaml",
        "rules": {
            "emails": bool(redact.get("emails", True)),
            "phones": bool(redact.get("phones", True)),
            "names": bool(redact.get("names", True)),
        },
    }


def build_prompt_observability(generation_meta: dict[str, Any]) -> dict[str, Any]:
    jobs = generation_meta.get("llm_job_log") or []
    stages = sorted({str(job.get("stage") or "") for job in jobs if job.get("stage")})
    models = sorted({str(job.get("model") or "") for job in jobs if job.get("model")})
    prompt_versions = sorted({str(job.get("prompt_version") or "") for job in jobs if job.get("prompt_version")})
    total_tokens = sum(
        int(job.get("total_tokens") or (int(job.get("input_tokens") or 0) + int(job.get("output_tokens") or 0)))
        for job in jobs
    )
    return {
        "llm_used": bool(generation_meta.get("llm_used")),
        "llm_model": generation_meta.get("llm_model"),
        "prompt_version": generation_meta.get("prompt_version"),
        "job_count": len(jobs),
        "stages": stages,
        "models": models,
        "prompt_versions": prompt_versions,
        "total_tokens": total_tokens,
    }


def build_review_summary(framework: dict[str, Any]) -> dict[str, Any]:
    lang = _framework_language(framework)
    view = resolve_customer_view(framework, lang=lang)
    open_items = framework.get("open_items") or []
    scores = framework.get("quality_scores") or {}
    render = framework.get("render") or {}
    confirm_check = _confirm_check_state(framework)

    assumptions = [_open_item_summary(item) for item in open_items if item.get("item_type") == "assumption"]
    open_questions = [_open_item_summary(item) for item in open_items if item.get("item_type") == "dependency"]
    contradictions = [_open_item_summary(item) for item in open_items if item.get("item_type") == "conflict"]
    evidence_warnings = _evidence_warnings(framework.get("chapters") or [])
    blocking_items = _blocking_items(framework, confirm_check, render)

    return {
        "language": lang,
        "headline": str(view.get("title") or framework.get("title") or "").strip(),
        "executive_summary": _executive_summary(view, framework),
        "key_pain_points": _key_pain_points(framework, view),
        "key_requirements": _key_requirements(framework, view),
        "target_outcomes": _target_outcomes(framework, view),
        "assumptions": assumptions,
        "open_questions": open_questions,
        "contradictions": contradictions,
        "evidence_warnings": evidence_warnings,
        "readiness": {
            "band": framework.get("readiness_band") or render.get("band"),
            "status_label": (framework.get("cover") or {}).get("status_label"),
            "build_readiness": scores.get("build_readiness"),
            "conversation_quality": scores.get("conversation_quality"),
            "opportunity_rating": scores.get("opportunity_rating"),
            "render_allowed": bool(render.get("allowed")),
            "assumptions_banner": bool(render.get("assumptions_banner")),
        },
        "blocking_items": blocking_items,
        "score_rationale": scores.get("rationale") or {},
        "source_coverage": _source_coverage(framework.get("chapters") or []),
        "confirm_ready": confirm_check["ready"],
        "confirm_block_reason": confirm_check.get("reason"),
    }


def build_attention_bundle(framework: dict[str, Any]) -> dict[str, Any]:
    signals = build_attention_signals(framework)
    review_state = _resolve_review_state(framework, signals)
    return {
        "review_state": review_state,
        "signals": signals,
    }


def build_attention_signals(framework: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    scores = framework.get("quality_scores") or {}
    open_items = framework.get("open_items") or []
    chapters = framework.get("chapters") or []
    render = framework.get("render") or {}
    readiness = int(scores.get("build_readiness") or 0)
    conversation = int(scores.get("conversation_quality") or 0)
    confirm_check = _confirm_check_state(framework)

    if not confirm_check["ready"] and confirm_check.get("reason"):
        issue_kind = confirm_check.get("issue_kind") or _confirm_issue_kind(confirm_check["reason"])
        if issue_kind == "contradiction":
            signals.append(
                _signal(
                    REVIEW_STATE_BLOCKING,
                    severity="blocking",
                    message=confirm_check["reason"],
                    action="Fix the contradiction in chapter 6 before approval.",
                    chapter_id="6",
                    fields=["chapters.6.body.ai_split"],
                )
            )
        else:
            signals.append(
                _signal(
                    REVIEW_STATE_MISSING,
                    severity="blocking",
                    message=confirm_check["reason"],
                    action="Complete chapter 6 AI used/not-used split before approval.",
                    chapter_id="6",
                    fields=["chapters.6.body.ai_split"],
                )
            )

    if not render.get("allowed"):
        signals.append(
            _signal(
                REVIEW_STATE_MISSING,
                severity="blocking",
                message=render.get("reason")
                or f"Build-readiness is {readiness}/100. Required information is still missing.",
                action="Close the open items in chapter 11 before approval.",
                chapter_id="11",
            )
        )

    dependencies = [item for item in open_items if item.get("item_type") == "dependency"]
    if dependencies:
        signals.append(
            _signal(
                REVIEW_STATE_MISSING,
                severity="blocking" if len(dependencies) >= 3 else "warning",
                message=f"{len(dependencies)} open question(s) still need client input.",
                action="Review chapter 11 and chapter 7 before approval.",
                chapter_id="11",
                count=len(dependencies),
            )
        )

    weak_chapters = [
        str(chapter.get("chapter_id"))
        for chapter in chapters
        if str(chapter.get("chapter_id")) not in {"0", "13"} and not chapter.get("source_refs")
    ]
    if weak_chapters:
        signals.append(
            _signal(
                REVIEW_STATE_WEAK_EVIDENCE,
                severity="warning" if len(weak_chapters) <= 2 else "blocking",
                message=f"{len(weak_chapters)} chapter(s) lack source references.",
                action="Regenerate weak chapters or add traceable facts.",
                chapter_id=weak_chapters[0],
                fields=[f"chapters.{chapter_id}.source_refs" for chapter_id in weak_chapters[:5]],
                count=len(weak_chapters),
            )
        )

    if not _executive_summary(resolve_customer_view(framework, lang=_framework_language(framework)), framework):
        signals.append(
            _signal(
                REVIEW_STATE_MISSING,
                severity="warning",
                message="Executive summary is empty.",
                action="Edit chapter 1 or regenerate it before approval.",
                chapter_id="1",
                fields=["chapters.1.body"],
            )
        )

    if conversation < 50:
        signals.append(
            _signal(
                REVIEW_STATE_WEAK_EVIDENCE,
                severity="warning",
                message=f"Conversation quality is {conversation}/100.",
                action="Upload a richer discovery transcript or regenerate weak chapters.",
            )
        )

    assumptions = [item for item in open_items if item.get("item_type") == "assumption"]
    if render.get("assumptions_banner") or assumptions:
        signals.append(
            _signal(
                REVIEW_STATE_RECOMMENDED,
                severity="info" if not assumptions else "warning",
                message=(
                    f"Build-readiness is {readiness}/100 with documented assumptions."
                    if assumptions
                    else "Assumptions apply to this framework."
                ),
                action="Review assumptions in chapter 11 before approval.",
                chapter_id="11",
                count=len(assumptions),
            )
        )

    if not signals:
        signals.append(
            _signal(
                REVIEW_STATE_READY,
                severity="info",
                message="No blocking issues detected. Human approval is still required.",
                action="Review the summary, then approve when ready.",
            )
        )

    return _dedupe_signals(signals)


def build_review_payload(framework: dict[str, Any]) -> dict[str, Any]:
    meta = framework.get("generation_meta") or {}
    attention = framework.get("attention") or build_attention_bundle(framework)
    return {
        "review_summary": framework.get("review_summary") or build_review_summary(framework),
        "attention": attention,
        "attention_signals": attention["signals"],
        "review_state": attention["review_state"],
        "prompt_observability": meta.get("prompt_observability") or build_prompt_observability(meta),
        "pii_handling": meta.get("pii_handling") or build_pii_handling_meta(),
        "generation_log": meta.get("llm_job_log") or [],
    }


def opportunity_pii_redaction_enabled(opportunity: dict[str, Any]) -> bool:
    if "pii_redaction_enabled" not in opportunity:
        return True
    return bool(opportunity.get("pii_redaction_enabled"))


def _resolve_review_state(framework: dict[str, Any], signals: list[dict[str, Any]]) -> str:
    ids = {str(signal["id"]) for signal in signals}
    if REVIEW_STATE_BLOCKING in ids:
        return REVIEW_STATE_BLOCKING
    if REVIEW_STATE_MISSING in ids and any(signal.get("severity") == "blocking" for signal in signals if signal["id"] == REVIEW_STATE_MISSING):
        return REVIEW_STATE_MISSING
    if REVIEW_STATE_WEAK_EVIDENCE in ids and any(
        signal.get("severity") == "blocking" for signal in signals if signal["id"] == REVIEW_STATE_WEAK_EVIDENCE
    ):
        return REVIEW_STATE_WEAK_EVIDENCE
    if REVIEW_STATE_MISSING in ids or REVIEW_STATE_WEAK_EVIDENCE in ids:
        return REVIEW_STATE_RECOMMENDED if REVIEW_STATE_RECOMMENDED in ids else REVIEW_STATE_MISSING
    if REVIEW_STATE_RECOMMENDED in ids:
        return REVIEW_STATE_RECOMMENDED
    return REVIEW_STATE_READY


def _framework_language(framework: dict[str, Any]) -> str:
    return str(
        framework.get("language")
        or (framework.get("customer_view") or {}).get("render_language")
        or framework.get("language_master")
        or "en"
    )


def _executive_summary(view: dict[str, Any], framework: dict[str, Any]) -> str:
    for chapter in view.get("chapters") or []:
        if str(chapter.get("chapter_id")) != "1":
            continue
        body = chapter.get("body")
        if isinstance(body, str) and body.strip():
            return body.strip()
        if isinstance(body, list):
            parts = _block_text_parts(body)
            if parts:
                return " ".join(parts).strip()
    return _management_summary_excerpt(framework)


def _key_pain_points(framework: dict[str, Any], view: dict[str, Any]) -> list[str]:
    points: list[str] = []
    for item in framework.get("open_items") or []:
        text = str(item.get("description") or item.get("item") or "").strip()
        if text and item.get("item_type") in {"dependency", "conflict"}:
            points.append(text)
    for kpi in framework.get("kpis") or []:
        name = str(kpi.get("name") or kpi.get("metric") or "").strip()
        if name:
            points.append(name)
    if not points:
        points.extend(_chapter_bullet_items(view, "2"))
    return _unique_nonempty(points, limit=5)


def _key_requirements(framework: dict[str, Any], view: dict[str, Any]) -> list[str]:
    requirements: list[str] = []
    for need in framework.get("access_needs") or []:
        if isinstance(need, dict):
            label = str(need.get("category") or need.get("need") or need.get("description") or "").strip()
            detail = str(need.get("specifically") or need.get("detail") or "").strip()
            requirements.append(": ".join(part for part in (label, detail) if part))
        elif isinstance(need, str) and need.strip():
            requirements.append(need.strip())
    if not requirements:
        requirements.extend(_chapter_bullet_items(view, "7"))
    return _unique_nonempty(requirements, limit=6)


def _target_outcomes(framework: dict[str, Any], view: dict[str, Any]) -> list[str]:
    outcomes: list[str] = []
    for kpi in framework.get("kpis") or []:
        target = str(kpi.get("target") or kpi.get("aim") or "").strip()
        name = str(kpi.get("name") or kpi.get("metric") or "").strip()
        if target and name:
            outcomes.append(f"{name}: {target}")
        elif name:
            outcomes.append(name)
    if not outcomes:
        outcomes.extend(_chapter_bullet_items(view, "3"))
    return _unique_nonempty(outcomes, limit=5)


def _blocking_items(
    framework: dict[str, Any],
    confirm_check: dict[str, Any],
    render: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not confirm_check["ready"] and confirm_check.get("reason"):
        items.append(
            {
                "kind": "confirm_gate",
                "chapter_id": "6",
                "message": confirm_check["reason"],
            }
        )
    if not render.get("allowed") and render.get("reason"):
        items.append(
            {
                "kind": "readiness",
                "chapter_id": "11",
                "message": str(render["reason"]),
            }
        )
    for item in framework.get("open_items") or []:
        if item.get("item_type") == "conflict":
            items.append(
                {
                    "kind": "contradiction",
                    "chapter_id": str(item.get("chapter_id") or "11"),
                    "message": str(item.get("description") or item.get("item") or "Unresolved contradiction"),
                }
            )
    return items


def _evidence_warnings(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for chapter in chapters:
        chapter_id = str(chapter.get("chapter_id") or "")
        if chapter_id in {"0", "13"}:
            continue
        if chapter.get("source_refs"):
            continue
        warnings.append(
            {
                "chapter_id": chapter_id,
                "title": str(chapter.get("title") or ""),
                "message": f"Chapter {chapter_id} has no source references.",
            }
        )
    return warnings


def _open_item_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_type": item.get("item_type"),
        "description": str(item.get("description") or item.get("item") or "").strip(),
        "owner": item.get("owner"),
        "status": item.get("status"),
        "chapter_id": item.get("chapter_id"),
    }


def _chapter_bullet_items(view: dict[str, Any], chapter_id: str) -> list[str]:
    for chapter in view.get("chapters") or []:
        if str(chapter.get("chapter_id")) != chapter_id:
            continue
        body = chapter.get("body")
        if not isinstance(body, list):
            return []
        items: list[str] = []
        for block in body:
            if not isinstance(block, dict):
                continue
            if block.get("block") == "bullets":
                items.extend(str(item).strip() for item in block.get("items") or [] if str(item).strip())
            else:
                items.extend(_block_text_parts([block]))
        return items
    return []


def _block_text_parts(blocks: list[dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    for block in blocks:
        for key in ("summary", "text", "lead", "caption"):
            value = block.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
    return parts


def _management_summary_excerpt(framework: dict[str, Any]) -> str:
    try:
        chapter = chapter_by_id(framework, "1")
    except ChapterValidationError:
        return ""
    body = chapter.get("body")
    if isinstance(body, str):
        return body.strip()
    if isinstance(body, list):
        return " ".join(_block_text_parts(body)).strip()
    return ""


def _confirm_check_state(framework: dict[str, Any]) -> dict[str, Any]:
    if str(framework.get("status") or "") == "confirmed":
        return {"ready": True, "reason": None, "issue_kind": None}
    probe = dict(framework)
    try:
        pre_confirm_check(probe)
    except PreConfirmError as exc:
        return {
            "ready": False,
            "reason": exc.user_message,
            "issue_kind": _confirm_issue_kind(exc.user_message),
        }
    except ChapterValidationError as exc:
        return {
            "ready": False,
            "reason": exc.user_message,
            "issue_kind": "missing",
        }
    return {"ready": True, "reason": None, "issue_kind": None}


def _confirm_issue_kind(message: str) -> str:
    lower = message.lower()
    if "contradict" in lower:
        return "contradiction"
    return "missing"


def _source_coverage(chapters: list[dict[str, Any]]) -> dict[str, int]:
    with_refs = sum(1 for chapter in chapters if chapter.get("source_refs"))
    return {
        "chapters_with_refs": with_refs,
        "chapters_total": len(chapters),
        "chapters_missing_refs": max(len(chapters) - with_refs, 0),
    }


def _signal(
    signal_id: str,
    *,
    severity: str,
    message: str,
    action: str,
    chapter_id: str | None = None,
    fields: list[str] | None = None,
    count: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": signal_id,
        "severity": severity,
        "message": message,
        "action": action,
    }
    if chapter_id is not None:
        payload["chapter_id"] = chapter_id
    if fields:
        payload["fields"] = fields
    if count is not None:
        payload["count"] = count
    return payload


def _dedupe_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str | None]] = set()
    unique: list[dict[str, Any]] = []
    for signal in signals:
        key = (str(signal["id"]), signal.get("chapter_id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(signal)
    severity_order = {"blocking": 0, "warning": 1, "info": 2}
    return sorted(unique, key=lambda item: (severity_order.get(str(item.get("severity")), 99), str(item["id"])))


def _unique_nonempty(values: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
        if len(unique) >= limit:
            break
    return unique


def _load_pii_config() -> dict[str, Any]:
    if not _PII_CONFIG_PATH.is_file():
        return {"default_enabled": True, "redact": {"emails": True, "phones": True, "names": True}}
    return yaml.safe_load(_PII_CONFIG_PATH.read_text(encoding="utf-8")) or {}
