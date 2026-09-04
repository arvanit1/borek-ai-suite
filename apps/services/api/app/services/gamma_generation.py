"""Policy-enforced Gamma generation boundary (AT-60 foundation)."""

from __future__ import annotations

from dataclasses import replace

from services.gamma.contract import (
    GammaContentSlot,
    GammaGenerateRequest,
    GammaGenerateResult,
    GammaPayloadError,
    GammaProvider,
)
from services.security.egress_filter import EgressPolicy, filter_external_payload


def generate_with_egress_policy(
    request: GammaGenerateRequest,
    *,
    provider: GammaProvider,
    policy: EgressPolicy | None = None,
    slot_classifications: dict[str, str],
) -> GammaGenerateResult:
    """Filter every dynamic content slot before invoking Gamma.

    Branding and layout are not part of this payload; they stay locked in the
    approved Gamma template. A blocked slot fails the request rather than
    silently producing an incomplete client document.
    """

    if policy is None:
        from services.security.egress_policy import load_runtime_egress_policy

        policy = load_runtime_egress_policy()
    slot_payload = {"slots": {slot.name: slot.value for slot in request.slots}}
    classifications = {
        f"/slots/{name}": classification
        for name, classification in slot_classifications.items()
    }
    from services.security.egress_audit import record_egress_decision

    decision = filter_external_payload(
        slot_payload,
        provider="gamma",
        classifications=classifications,
        policy=policy,
    )
    record_egress_decision(
        provider="gamma",
        stage="gamma_rendering",
        allowed_paths=decision.allowed_paths,
        blocked_paths=decision.blocked_paths,
    )
    if decision.blocked_paths:
        raise GammaPayloadError(
            "Gamma payload contains blocked or unclassified fields: "
            + ", ".join(decision.blocked_paths)
        )

    filtered_slots = decision.payload.get("slots", {})
    safe_request = replace(
        request,
        slots=tuple(
            GammaContentSlot(name=name, value=value)
            for name, value in filtered_slots.items()
        ),
    )
    return provider.generate(safe_request)
