"""Authoritative Gamma provider-egress inventory (BT-32).

Classifies what actually leaves Borek on a Gamma send, not the ES-40
intermediate payload. Raw ``prior_stage_context`` and ``grounded_facts``
are not sent today and stay unclassified so a future leak fails closed.
"""

from __future__ import annotations

from typing import Any

from services.gamma.contract import GammaGenerateRequest, gamma_egress_reference
from services.gamma.signed_logo import owned_https_prefixes

# Content-bearing HTTP keys. inputText/title are flattened from classified slots.
GAMMA_LIVE_HTTP_KEYS = frozenset(
    {
        "inputText",
        "prompt",
        "title",
        "textMode",
        "format",
        "themeId",
        "exportAs",
        "cardOptions",
        "gammaId",
    }
)

GAMMA_TECHNICAL_HTTP_KEYS = frozenset(
    {"textMode", "format", "themeId", "exportAs", "gammaId"}
)

# These roots are internal payload objects. They must not appear on a provider send.
FORBIDDEN_RAW_EGRESS_ROOTS = ("prior_stage_context", "grounded_facts")


def fetchable_client_logo_url(request: GammaGenerateRequest) -> str | None:
    return gamma_egress_reference(
        request.client_logo_ref,
        owned_https_prefixes=owned_https_prefixes(),
    )


def gamma_content_egress_inventory(request: GammaGenerateRequest) -> dict[str, Any]:
    """Named slots plus a fetchable client-logo URL. No Framework / fact objects."""
    inventory: dict[str, Any] = {
        "slots": {slot.name: slot.value for slot in request.slots},
    }
    logo_url = fetchable_client_logo_url(request)
    if logo_url is not None:
        inventory["client_logo_url"] = logo_url
    return inventory


def gamma_live_technical_inventory(
    *,
    theme_id: str,
    template_id: str,
    output_format: str,
) -> dict[str, Any]:
    provider: dict[str, str] = {
        "themeId": theme_id,
        "exportAs": output_format,
    }
    if template_id:
        provider["gammaId"] = template_id
    else:
        provider["textMode"] = "preserve"
        provider["format"] = "presentation"
    return {"provider": provider}


def gamma_live_egress_inventory(
    request: GammaGenerateRequest,
    *,
    theme_id: str,
    template_id: str,
) -> dict[str, Any]:
    inventory = gamma_content_egress_inventory(request)
    inventory.update(
        gamma_live_technical_inventory(
            theme_id=theme_id,
            template_id=template_id,
            output_format=request.output_formats[0],
        )
    )
    return inventory
