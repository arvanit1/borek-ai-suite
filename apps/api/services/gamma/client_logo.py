"""JJ-27: where an uploaded client logo appears in a Gamma deck, and what
happens when it is missing or too poor to place.

The Borek logo is part of the locked template and is never affected by any of
this. The client logo is co-branding: it appears bottom-right on the cover and
closing cards only, never on content cards. A logo that fails the quality gate
is dropped rather than stretched, and the cover falls back to the client name
wordmark that `cover.client_name` already carries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.gamma.template import GammaLogoRules, load_gamma_template

ARTIFACT_LOGO_PREFIX = "artifact:logos/"

# Reasons are stable strings: they end up in job metadata and ops dashboards.
REASON_APPLIED = "applied"
REASON_APPLIED_ON_PLATE = "applied_on_white_plate"
REASON_MISSING = "missing"
REASON_DIMENSIONS_UNKNOWN = "dimensions_unknown"
REASON_BELOW_MIN_EDGE = "below_minimum_resolution"
REASON_INSUFFICIENT_PIXELS = "insufficient_pixels"
REASON_EXTREME_ASPECT_RATIO = "extreme_aspect_ratio"

FALLBACK_WORDMARK = "client_name_wordmark"


@dataclass(frozen=True)
class ClientLogoPlacement:
    """Resolved geometry for the client logo, relative to the card."""

    cards: tuple[str, ...]
    position: str
    max_height_pct: float
    min_clear_space_pct: float
    co_brand_with_borek_logo: bool
    backdrop: str  # "none" or "white_plate" for formats without transparency


@dataclass(frozen=True)
class ClientLogoDecision:
    applied: bool
    reason: str
    detail: str
    reference: str | None = None
    placement: ClientLogoPlacement | None = None
    fallback: str | None = None

    def as_metadata(self) -> dict[str, Any]:
        """Job-safe summary. Carries no bytes and no storage path."""
        return {
            "applied": self.applied,
            "reason": self.reason,
            "detail": self.detail,
            "fallback": self.fallback,
            "position": self.placement.position if self.placement else None,
            "cards": list(self.placement.cards) if self.placement else [],
            "backdrop": self.placement.backdrop if self.placement else None,
        }


def decide_client_logo(
    metadata: dict[str, Any] | None,
    *,
    opportunity_id: Any,
    rules: GammaLogoRules | None = None,
) -> ClientLogoDecision:
    """Apply the JJ-27 placement rules to one opportunity's stored logo."""
    gate = rules or load_gamma_template().client_logo

    if not metadata:
        return _fallback(REASON_MISSING, "No client logo is stored for this opportunity.")

    width = _positive_int(metadata.get("width_px"))
    height = _positive_int(metadata.get("height_px"))
    if width is None or height is None:
        return _fallback(
            REASON_DIMENSIONS_UNKNOWN,
            "Stored logo has no recorded pixel dimensions, so it cannot be sized safely.",
        )

    shortest = min(width, height)
    if shortest < gate.min_edge_px:
        return _fallback(
            REASON_BELOW_MIN_EDGE,
            f"Logo shortest edge is {shortest}px, below the {gate.min_edge_px}px minimum.",
        )
    if width * height < gate.min_placement_area_px:
        return _fallback(
            REASON_INSUFFICIENT_PIXELS,
            f"Logo is {width}x{height}px, below the "
            f"{gate.min_placement_area_px}px minimum placement area.",
        )
    aspect = max(width, height) / min(width, height)
    if aspect > gate.max_aspect_ratio:
        return _fallback(
            REASON_EXTREME_ASPECT_RATIO,
            f"Logo aspect ratio {aspect:.1f}:1 exceeds the "
            f"{gate.max_aspect_ratio:.0f}:1 limit for the co-branding area.",
        )

    mime_type = str(metadata.get("mime_type") or "").lower()
    opaque = mime_type in gate.opaque_formats
    placement = ClientLogoPlacement(
        cards=gate.cards,
        position=gate.position,
        max_height_pct=gate.max_height_pct,
        min_clear_space_pct=gate.min_clear_space_pct,
        co_brand_with_borek_logo=gate.co_brand_with_borek_logo,
        backdrop="white_plate" if opaque else "none",
    )
    return ClientLogoDecision(
        applied=True,
        reason=REASON_APPLIED_ON_PLATE if opaque else REASON_APPLIED,
        detail=(
            f"Placed {gate.position} on {', '.join(gate.cards)} at up to "
            f"{gate.max_height_pct:.0f}% card height"
            + (" on a white plate because the upload has no transparency." if opaque else ".")
        ),
        reference=f"{ARTIFACT_LOGO_PREFIX}{opportunity_id}",
        placement=placement,
    )


def _fallback(reason: str, detail: str) -> ClientLogoDecision:
    return ClientLogoDecision(
        applied=False,
        reason=reason,
        detail=detail,
        fallback=FALLBACK_WORDMARK,
    )


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
