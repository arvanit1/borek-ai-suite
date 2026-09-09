"""AT-60 Gamma pipeline stage: flag, adapter, persist, observe, retry."""

from __future__ import annotations

import time
import uuid
from typing import Any
from uuid import UUID

from app.config import settings
from app.services.gamma_generation import generate_with_egress_policy
from services.gamma.artifacts import gamma_result_metadata, persist_gamma_result
from services.gamma.client_logo import (
    FALLBACK_WORDMARK,
    ClientLogoDecision,
    decide_client_logo,
)
from services.gamma.contract import (
    LOCKED_BOREK_TEMPLATE_ID,
    LOCKED_BOREK_TEMPLATE_VERSION,
    GammaError,
    GammaGenerateRequest,
)
from services.gamma.provider import build_gamma_provider
from services.gamma.payload import build_gamma_content_payload, slots_from_payload
from services.gamma.slot_mapping import DEFAULT_JOURNEY_STAGE, slot_chapter_provenance
from services.observability.llm_logger import llm_observability_scope, log_llm_call
from services.security.egress_policy import load_runtime_egress_policy, slot_classifications_from_policy


def presentation_engine() -> str:
    return settings.PRESENTATION_ENGINE


def gamma_enabled() -> bool:
    return presentation_engine() == "gamma"


def client_logo_decision_for_opportunity(
    store: Any,
    *,
    opportunity_id: UUID,
    user_id: UUID,
) -> ClientLogoDecision:
    """JJ-27: read the stored logo metadata and apply the placement rules."""
    getter = getattr(store, "get_client_logo", None)
    metadata: dict[str, Any] | None = None
    if getter is not None:
        try:
            metadata = getter(opportunity_id=opportunity_id, user_id=user_id)
        except Exception:
            metadata = None
    return decide_client_logo(metadata, opportunity_id=opportunity_id)


def build_gamma_request(
    *,
    opportunity: dict[str, Any],
    presentation_version_id: UUID | str,
    user_id: UUID,
    store: Any,
    framework: dict[str, Any] | None = None,
    output_formats: tuple[str, ...] = ("pptx", "pdf"),
) -> tuple[GammaGenerateRequest, ClientLogoDecision]:
    opportunity_id = opportunity["id"]
    logo = client_logo_decision_for_opportunity(
        store,
        opportunity_id=opportunity_id if isinstance(opportunity_id, UUID) else UUID(str(opportunity_id)),
        user_id=user_id,
    )
    stage = str(opportunity.get("journey_stage") or DEFAULT_JOURNEY_STAGE)
    content = build_gamma_content_payload(
        opportunity=opportunity,
        framework=framework,
        stage=stage,
        client_logo_ref=logo.reference,
    )
    request = GammaGenerateRequest(
        template_id=LOCKED_BOREK_TEMPLATE_ID,
        template_version=LOCKED_BOREK_TEMPLATE_VERSION,
        opportunity_id=str(opportunity_id),
        presentation_version_id=str(presentation_version_id),
        output_formats=output_formats,  # type: ignore[arg-type]
        slots=slots_from_payload(content),
        client_logo_ref=content.get("client_logo_ref"),
        client_logo_placement=logo.placement if content.get("client_logo_ref") else None,
        timeout_seconds=settings.GAMMA_TIMEOUT_SECONDS,
    )
    return request, logo


def run_gamma_rendering_stage(
    store: Any,
    *,
    job_id: UUID,
    opportunity: dict[str, Any],
    presentation_version_id: UUID | str,
    user_id: UUID,
    framework: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not gamma_enabled():
        return {"skipped": True, "engine": "internal"}

    request, logo = build_gamma_request(
        opportunity=opportunity,
        presentation_version_id=presentation_version_id,
        user_id=user_id,
        store=store,
        framework=framework,
    )
    provider = build_gamma_provider(
        execution_mode=settings.GAMMA_EXECUTION_MODE,
        api_key=settings.GAMMA_API_KEY,
        base_url=settings.GAMMA_API_BASE_URL,
        theme_id=settings.GAMMA_THEME_ID,
        template_id=settings.GAMMA_TEMPLATE_ID,
    )
    classifications = slot_classifications_from_policy(tuple(slot.name for slot in request.slots))
    started = time.monotonic()
    retry_count = 0
    with llm_observability_scope(
        job_id=job_id,
        opportunity_id=opportunity["id"],
        store=store,
    ):
        return _invoke_gamma(
            request,
            provider=provider,
            classifications=classifications,
            started=started,
            retry_count=retry_count,
            job_id=job_id,
            opportunity=opportunity,
            logo=logo,
        )


def _client_logo_metadata(
    logo: ClientLogoDecision,
    *,
    provider_applied: bool,
) -> dict[str, Any]:
    """Record what the deck actually shows, not just what the rules allowed."""
    metadata = logo.as_metadata()
    if logo.applied and not provider_applied:
        metadata.update(
            applied=False,
            reason="provider_could_not_fetch_reference",
            detail=(
                "The stored logo passed the placement rules but the reference is "
                "private, so the deck falls back to the client name wordmark."
            ),
            fallback=FALLBACK_WORDMARK,
        )
    return metadata


def _invoke_gamma(
    request: GammaGenerateRequest,
    *,
    provider,
    classifications: dict[str, str],
    started: float,
    retry_count: int,
    job_id: UUID,
    opportunity: dict[str, Any],
    logo: ClientLogoDecision,
) -> dict[str, Any]:
    try:
        result = generate_with_egress_policy(
            request,
            provider=provider,
            policy=load_runtime_egress_policy(),
            slot_classifications=classifications,
        )
        persisted = persist_gamma_result(result, artifact_root=settings.ARTIFACT_ROOT)
        log_llm_call(
            request_id=uuid.uuid4(),
            stage="gamma_rendering",
            model="gamma-api",
            prompt_version=request.template_version,
            input_tokens=0,
            output_tokens=0,
            latency_ms=(time.monotonic() - started) * 1000,
            retry_count=retry_count,
            job_id=job_id,
            opportunity_id=opportunity["id"],
            provider="gamma",
            status="success",
            estimated_cost_eur=0.0,
        )
        metadata = gamma_result_metadata(persisted)
        return {
            "skipped": False,
            "engine": "gamma",
            "execution_mode": settings.GAMMA_EXECUTION_MODE,
            **metadata,
            "slot_source_chapters": {
                name: list(chapter_ids)
                for name, chapter_ids in slot_chapter_provenance(request.slots).items()
            },
            "client_logo": _client_logo_metadata(
                logo,
                provider_applied=bool(metadata.get("client_logo_applied")),
            ),
        }
    except GammaError as exc:
        log_llm_call(
            request_id=uuid.uuid4(),
            stage="gamma_rendering",
            model="gamma-api",
            prompt_version=request.template_version,
            input_tokens=0,
            output_tokens=0,
            latency_ms=(time.monotonic() - started) * 1000,
            retry_count=retry_count,
            job_id=job_id,
            opportunity_id=opportunity["id"],
            provider="gamma",
            status="error",
            error_category=exc.classification,
            estimated_cost_eur=0.0,
        )
        raise


def run_gamma_stage_for_presentation(
    store: Any,
    *,
    job_id: UUID,
    presentation_id: UUID | str,
    user_id: UUID | str,
    presentation_version_id: UUID | str,
) -> dict[str, Any]:
    if not gamma_enabled():
        return {"skipped": True, "engine": "internal"}
    parsed_user = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
    parsed_presentation = (
        presentation_id if isinstance(presentation_id, UUID) else UUID(str(presentation_id))
    )
    resolver = getattr(store, "get_presentation_opportunity_id", None)
    if resolver is not None:
        opportunity_id = resolver(presentation_id=parsed_presentation, user_id=parsed_user)
    else:
        presentation = store.get_presentation(
            presentation_id=parsed_presentation,
            user_id=parsed_user,
        )
        opportunity_id = presentation["opportunity_id"]
    opportunity = store.get_opportunity(
        opportunity_id=opportunity_id,
        user_id=parsed_user,
    )
    framework = None
    getter = getattr(store, "get_latest_framework", None)
    if getter is not None:
        try:
            framework = getter(
                opportunity_id=opportunity_id,
                user_id=parsed_user,
            )
        except Exception:
            framework = None
    return run_gamma_rendering_stage(
        store,
        job_id=job_id,
        opportunity=opportunity,
        presentation_version_id=presentation_version_id,
        user_id=parsed_user,
        framework=framework,
    )
