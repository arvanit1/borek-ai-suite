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
    LOCKED_BOREK_TEMPLATE_VERSION,
    GammaError,
    GammaGenerateRequest,
)
from services.gamma.signed_logo import mint_signed_client_logo_url
from services.gamma.provider import build_gamma_provider
from services.gamma.payload import build_gamma_content_payload, slots_from_payload
from services.gamma.slot_mapping import resolve_journey_stage, slot_chapter_provenance
from services.gamma.template import load_gamma_template
from services.observability.llm_logger import llm_observability_scope, log_llm_call
from services.security.egress_policy import load_runtime_egress_policy, slot_classifications_from_policy


KNOWN_PRESENTATION_ENGINES = frozenset({"internal", "gamma"})


class PresentationEngineConfigError(RuntimeError):
    """Invalid PRESENTATION_ENGINE. Fail closed; do not pick a renderer."""

    code = "PRESENTATION_ENGINE_INVALID"
    retryable = False


def presentation_engine() -> str:
    return settings.PRESENTATION_ENGINE


def require_presentation_engine() -> str:
    engine = presentation_engine()
    if engine not in KNOWN_PRESENTATION_ENGINES:
        raise PresentationEngineConfigError(
            f"PRESENTATION_ENGINE must be 'internal' or 'gamma'; got {engine!r}."
        )
    return engine


def gamma_enabled() -> bool:
    return require_presentation_engine() == "gamma"


def uses_internal_renderer() -> bool:
    """BT-28: configuration fallback. Not an automatic provider-failure fallback."""
    return require_presentation_engine() == "internal"


def _signed_logo_ref(
    logo: ClientLogoDecision,
    *,
    opportunity_id: Any,
    stage: str,
) -> str | None:
    """JJ-29: mint a fetchable URL only after the placement gate. Never send private refs."""
    profile = load_gamma_template().profile(stage)
    if not logo.applied or not profile.client_logo:
        return None
    ttl = max(int(settings.CLIENT_LOGO_SIGNED_URL_TTL_SECONDS), int(settings.GAMMA_TIMEOUT_SECONDS) + 60)
    return mint_signed_client_logo_url(
        opportunity_id,
        public_api_base_url=settings.PUBLIC_API_BASE_URL,
        secret=settings.CLIENT_LOGO_SIGNING_SECRET or settings.SUPABASE_JWT_SECRET,
        ttl_seconds=ttl,
    )


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
    stage: str | None = None,
    prior_stage_context: dict[str, Any] | None = None,
) -> tuple[GammaGenerateRequest, ClientLogoDecision]:
    opportunity_id = opportunity["id"]
    logo = client_logo_decision_for_opportunity(
        store,
        opportunity_id=opportunity_id if isinstance(opportunity_id, UUID) else UUID(str(opportunity_id)),
        user_id=user_id,
    )
    resolved_stage = resolve_journey_stage(
        stage
        or opportunity.get("journey_stage")
        or opportunity.get("requested_journey_stage")
    )
    opportunity["journey_stage"] = resolved_stage
    signed_ref = _signed_logo_ref(logo, opportunity_id=opportunity_id, stage=resolved_stage)
    content = build_gamma_content_payload(
        opportunity=opportunity,
        framework=framework,
        stage=resolved_stage,
        client_logo_ref=signed_ref,
        prior_stage_context=prior_stage_context or opportunity.get("prior_stage_context"),
    )
    request = GammaGenerateRequest(
        template_id=content["template_id"],
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
    stage: str | None = None,
    prior_stage_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not gamma_enabled():
        return {"skipped": True, "engine": "internal"}

    request, logo = build_gamma_request(
        opportunity=opportunity,
        presentation_version_id=presentation_version_id,
        user_id=user_id,
        store=store,
        framework=framework,
        stage=stage,
        prior_stage_context=prior_stage_context,
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
                for name, chapter_ids in slot_chapter_provenance(
                    request.slots,
                    stage=resolve_journey_stage(opportunity.get("journey_stage")),
                ).items()
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


def mark_version_ready_after_gamma(
    store: Any,
    version: dict[str, Any],
    gamma_result: dict[str, Any],
) -> dict[str, Any]:
    """JJ-28 downloads require status=ready. Do not invent internal PPTX/PDF paths."""
    if gamma_result.get("skipped") or not gamma_result.get("artifacts"):
        return version
    updater = getattr(store, "update_presentation_version_assets", None)
    if updater is None:
        version["status"] = "ready"
        return version
    try:
        return updater(
            presentation_version_id=version["id"],
            assets={
                "pptx_storage_path": version.get("pptx_storage_path"),
                "pdf_storage_path": version.get("pdf_storage_path"),
                "preview_image_paths": list(version.get("preview_image_paths") or []),
            },
            status="ready",
        )
    except Exception:
        version["status"] = "ready"
        return version


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
    version = None
    version_getter = getattr(store, "get_presentation_version", None)
    if version_getter is not None:
        parsed_version_id = (
            presentation_version_id
            if isinstance(presentation_version_id, UUID)
            else UUID(str(presentation_version_id))
        )
        try:
            version = version_getter(
                presentation_version_id=parsed_version_id,
                user_id=parsed_user,
            )
        except Exception:
            version = None
    stage = (version or {}).get("journey_stage") or opportunity.get("journey_stage")
    prior_stage_context = None
    if version is not None:
        from app.services.journey_stage import load_prior_stage_context_for_version

        prior_stage_context = load_prior_stage_context_for_version(
            store,
            opportunity=opportunity,
            version=version,
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
        stage=stage,
        prior_stage_context=prior_stage_context,
    )
