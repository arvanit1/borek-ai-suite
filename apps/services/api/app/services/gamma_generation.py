"""Policy-enforced Gamma generation boundary (AT-60 / BT-32)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from services.gamma.contract import (
    GammaContentSlot,
    GammaGenerateRequest,
    GammaGenerateResult,
    GammaPayloadError,
    GammaProvider,
)
from services.gamma.provider_egress import gamma_content_egress_inventory
from services.security.egress_audit import skip_nested_egress_records
from services.security.egress_filter import EgressPolicy
from services.security.egress_policy import EgressBlockedError, enforce_external_egress


def generate_with_egress_policy(
    request: GammaGenerateRequest,
    *,
    provider: GammaProvider,
    policy: EgressPolicy | None = None,
    slot_classifications: dict[str, str],
    store: Any | None = None,
    actor_id: Any | None = None,
    journey_stage: str | None = None,
    attempt: int = 1,
    pipeline_stage: str = "gamma_rendering",
) -> GammaGenerateResult:
    """Filter the real provider-egress inventory, audit once, then send.

    Branding and layout stay locked in the approved Gamma template. A blocked
    field fails the request rather than silently producing an incomplete deck.
    Nested live-client filtering does not write a second audit row.
    """

    extra = {f"/slots/{name}": classification for name, classification in slot_classifications.items()}
    inventory = gamma_content_egress_inventory(request)
    try:
        safe = enforce_external_egress(
            inventory,
            provider="gamma",
            stage=pipeline_stage,
            extra_classifications=extra,
            journey_stage=journey_stage,
            opportunity_id=request.opportunity_id,
            presentation_version_id=request.presentation_version_id,
            attempt=attempt,
            store=store,
            actor_id=actor_id,
            policy=policy,
        )
    except EgressBlockedError as exc:
        raise GammaPayloadError(
            "Gamma payload contains blocked or unclassified fields: "
            + ", ".join(exc.blocked_paths)
        ) from exc

    filtered_slots = safe.get("slots", {}) if isinstance(safe, dict) else {}
    if not isinstance(filtered_slots, dict):
        raise GammaPayloadError("Gamma payload contains blocked or unclassified fields.")
    logo_allowed = isinstance(safe, dict) and "client_logo_url" in safe
    safe_request = replace(
        request,
        slots=tuple(
            GammaContentSlot(name=name, value=value)
            for name, value in filtered_slots.items()
        ),
        client_logo_ref=request.client_logo_ref if logo_allowed else None,
        client_logo_placement=request.client_logo_placement if logo_allowed else None,
    )
    with skip_nested_egress_records():
        return provider.generate(safe_request)
