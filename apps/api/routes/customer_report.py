"""Customer report API. Technical-framework views are intentionally not implemented."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from config import settings
from services.framework.config_loader import repo_root
from services.framework.eligibility import RenderBlocked
from services.framework.pipeline import generate_customer_framework
from services.framework.pre_confirm_check import confirm_customer_report
from services.framework.regenerate_chapter import ChapterRegenError, regenerate_chapter
from services.framework.rendering.customer_pdf import render_customer_pdf, write_customer_pdf
from services.framework.store import (
    get_framework,
    knowledge_for,
    list_frameworks,
    save_framework,
    save_knowledge,
    save_transcript,
)
from services.knowledge_model.extraction import extract_knowledge_model
from services.observability.llm_logger import STAGE_EXTRACTION, jobs_for_opportunity
from services.transcript.conversation_ids import allocate_opportunity_id, allocate_transcript_identity
from services.transcript.speaker_turns import split_speaker_turns

router = APIRouter()


@router.post("/transcripts")
async def upload_transcript(
    file: UploadFile = File(...),
    opportunity_id: str | None = Form(default=None),
    conversation_id: str | None = Form(default=None),
    redact: bool = Form(default=True),
) -> dict[str, Any]:
    content = await file.read()
    turns = split_speaker_turns(file.filename or "transcript.txt", content)
    opp = allocate_opportunity_id(opportunity_id)
    taken = [item.get("conversation_id", "") for item in knowledge_for(opp)]
    identity = allocate_transcript_identity(opp, conversation_id=conversation_id, taken_conversation_ids=taken)
    print(f"ES-5 extraction started for {identity.conversation_id} ({len(turns)} turns)", flush=True)
    model = extract_knowledge_model(turns, identity, redact=redact)
    print(f"ES-5 extraction finished for {identity.conversation_id}", flush=True)
    save_knowledge(opp, model)
    save_transcript(
        {
            "opportunity_id": opp,
            "transcript_id": identity.transcript_id,
            "conversation_id": identity.conversation_id,
            "filename": file.filename,
            "turns": len(turns),
        }
    )
    return {
        "opportunity_id": opp,
        "transcript_id": identity.transcript_id,
        "conversation_id": identity.conversation_id,
        "knowledge_model": model,
        "generation_log": jobs_for_opportunity(opp, stages=[STAGE_EXTRACTION]),
    }


@router.post("/frameworks/generate")
def generate_framework(
    payload: dict[str, Any],
) -> dict[str, Any]:
    opportunity_id = str(payload.get("opportunity_id") or "").strip()
    if not opportunity_id:
        raise HTTPException(status_code=400, detail="opportunity_id is required.")
    models = knowledge_for(opportunity_id)
    if not models:
        raise HTTPException(status_code=404, detail="No knowledge models for this opportunity. Upload a transcript first.")
    lang = str(payload.get("lang") or "en")
    title_hint = payload.get("title")
    print(f"ES-9 generate started for {opportunity_id} use_llm=True", flush=True)
    framework = generate_customer_framework(
        models,
        opportunity_id=opportunity_id,
        title_hint=title_hint,
        lang=lang,
        use_llm=True,
        engine_overrides=payload.get("engine_overrides") or {},
    )
    save_framework(framework)
    print(f"ES-9 generate finished {framework.get('id')}", flush=True)
    return _public_framework(framework)


@router.post("/frameworks/demo")
def generate_demo() -> dict[str, Any]:
    """Invoice 3-way-match customer report via ES-5 + ES-9 (Claude Sonnet)."""
    transcript = (
        repo_root() / "tests" / "eval" / "fixtures" / "transcripts" / "invoice_3way_match.txt"
    )
    if not transcript.is_file():
        raise HTTPException(status_code=500, detail="Demo transcript fixture is missing.")
    content = transcript.read_bytes()
    turns = split_speaker_turns("invoice_3way_match.txt", content)
    opp = allocate_opportunity_id(None)
    identity = allocate_transcript_identity(opp, taken_conversation_ids=[])
    print(f"ES-5 demo extraction started for {identity.conversation_id} ({len(turns)} turns)", flush=True)
    model = extract_knowledge_model(turns, identity, redact=True)
    print(f"ES-5 demo extraction finished for {identity.conversation_id}", flush=True)
    save_knowledge(opp, model)
    save_transcript(
        {
            "opportunity_id": opp,
            "transcript_id": identity.transcript_id,
            "conversation_id": identity.conversation_id,
            "filename": "invoice_3way_match.txt",
            "turns": len(turns),
        }
    )
    print(f"ES-9 demo generate started for {opp} use_llm=True", flush=True)
    framework = generate_customer_framework(
        [model],
        opportunity_id=opp,
        title_hint="Invoice 3-Way Match",
        lang="en",
        use_llm=True,
    )
    save_framework(framework)
    print(f"ES-9 demo generate finished {framework.get('id')}", flush=True)
    return _public_framework(framework)


@router.get("/frameworks")
def list_all() -> dict[str, Any]:
    items = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "department": item.get("department"),
            "status": item.get("cover", {}).get("status_label"),
            "scores": item.get("quality_scores"),
            "render_allowed": (item.get("render") or {}).get("allowed"),
        }
        for item in list_frameworks()
    ]
    return {"frameworks": items}


@router.get("/frameworks/{framework_id}")
def get_one(
    framework_id: str,
    view: str = Query(default="customer"),
    lang: str = Query(default="en"),
) -> dict[str, Any]:
    if view == "technical":
        raise HTTPException(
            status_code=501,
            detail="The technical framework is out of scope for this service. Only the customer report is produced.",
        )
    framework = get_framework(framework_id)
    if not framework:
        raise HTTPException(status_code=404, detail="Framework not found.")
    if view == "canonical":
        payload = dict(framework)
        payload.pop("customer_view", None)
        return payload
    return framework.get("customer_view") or _public_framework(framework)


@router.post("/frameworks/{framework_id}/chapters/{chapter_id}/regenerate")
def regenerate_one(framework_id: str, chapter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """ES-12 — replace one chapter while preserving immutable prior versions on disk."""
    framework = _require(framework_id)
    chapter = payload.get("chapter")
    if not isinstance(chapter, dict):
        raise HTTPException(status_code=400, detail="chapter object is required.")
    reason = str(payload.get("reason") or "manual chapter refresh").strip()
    try:
        updated = regenerate_chapter(framework, chapter_id, chapter, reason=reason)
    except ChapterRegenError as exc:
        raise HTTPException(status_code=409, detail=exc.user_message) from exc
    save_framework(updated)
    return _public_framework(updated)


@router.post("/frameworks/{framework_id}/confirm")
def confirm(framework_id: str) -> dict[str, Any]:
    """Human sign-off for the customer report only. Blocked when chapter 6 AI-use is inconsistent."""
    framework = _require(framework_id)
    confirmed = confirm_customer_report(framework)
    save_framework(confirmed)
    return _public_framework(confirmed)


@router.get("/frameworks/{framework_id}/readiness")
def readiness(framework_id: str) -> dict[str, Any]:
    framework = _require(framework_id)
    return {
        "quality_scores": framework.get("quality_scores"),
        "assessments": framework.get("assessments"),
        "render": framework.get("render"),
        "open_items": framework.get("open_items"),
    }


@router.get("/frameworks/{framework_id}/gaps")
def gaps(framework_id: str) -> dict[str, Any]:
    framework = _require(framework_id)
    return {
        "open_items": framework.get("open_items") or [],
        "unknowns": [
            item for item in framework.get("open_items") or [] if item.get("item_type") == "assumption"
        ],
    }


@router.post("/frameworks/{framework_id}/render")
def render(framework_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    framework = _require(framework_id)
    body = payload or {}
    if body.get("view") == "technical":
        raise HTTPException(status_code=501, detail="Technical framework rendering is out of scope.")
    lang = str(body.get("lang") or framework.get("customer_view", {}).get("render_language") or "en")
    pdf = render_customer_pdf(framework, lang=lang)
    out = settings.artifact_dir / f"{framework_id}.pdf"
    write_customer_pdf(framework, out, lang=lang)
    return {
        "framework_id": framework_id,
        "format": "pdf",
        "bytes": len(pdf),
        "path": str(out),
        "download": f"/frameworks/{framework_id}/pdf?lang={lang}",
    }


@router.get("/frameworks/{framework_id}/pdf")
def download_pdf(framework_id: str, lang: str = Query(default="en")) -> Response:
    framework = _require(framework_id)
    try:
        pdf = render_customer_pdf(framework, lang=lang)
    except RenderBlocked as exc:
        raise HTTPException(status_code=409, detail=exc.user_message) from exc
    filename = f"{framework_id}-customer-report.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _require(framework_id: str) -> dict[str, Any]:
    framework = get_framework(framework_id)
    if not framework:
        raise HTTPException(status_code=404, detail="Framework not found.")
    return framework


def _public_framework(framework: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": framework.get("id"),
        "opportunity_id": framework.get("opportunity_id"),
        "title": framework.get("title"),
        "department": framework.get("department"),
        "status": framework.get("status"),
        "cover": framework.get("cover"),
        "quality_scores": framework.get("quality_scores"),
        "render": framework.get("render"),
        "kpis": framework.get("kpis"),
        "systems": framework.get("systems"),
        "rules": framework.get("rules"),
        "exceptions": framework.get("exceptions"),
        "access_needs": framework.get("access_needs"),
        "evolution_stages": framework.get("evolution_stages"),
        "open_items": framework.get("open_items"),
        "estimate": framework.get("estimate"),
        "business_case": framework.get("business_case"),
        "chapters": (framework.get("customer_view") or framework).get("chapters"),
        "generation_meta": framework.get("generation_meta"),
        "generation_log": (framework.get("generation_meta") or {}).get("llm_job_log") or [],
        "version": framework.get("version"),
    }
