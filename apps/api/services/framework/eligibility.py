"""Eligibility and customer-report render gates."""

from __future__ import annotations

from typing import Any

from services.framework.config_loader import scoring_config


class EligibilityError(ValueError):
    def __init__(self, message: str, gaps: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.user_message = message
        self.gaps = gaps or []


class RenderBlocked(ValueError):
    def __init__(self, message: str, readiness: int, gaps: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.user_message = message
        self.readiness = readiness
        self.gaps = gaps or []


def check_eligibility(
    *,
    conversation_quality: int,
    has_knowledge: bool,
    gaps: list[dict[str, Any]] | None = None,
) -> None:
    cfg = scoring_config()
    minimum = int(cfg["eligibility"]["min_conversation_quality"])
    if not has_knowledge:
        raise EligibilityError(
            "No knowledge model is available. Capture a conversation before generating a customer report.",
            gaps=gaps or [],
        )
    if conversation_quality < minimum:
        raise EligibilityError(
            f"Conversation quality is {conversation_quality}/100. "
            f"It must be at least {minimum} before a framework is generated.",
            gaps=gaps or [],
        )


def render_decision(readiness_score: int, open_items: list[dict[str, Any]]) -> dict[str, Any]:
    cfg = scoring_config()["build_readiness"]["bands"]
    not_ready = int(cfg["not_ready"])
    ready_with_assumptions = int(cfg["ready_with_assumptions"])
    if readiness_score < not_ready:
        return {
            "allowed": False,
            "assumptions_banner": False,
            "band": "not_ready",
            "reason": (
                f"Build-readiness is {readiness_score}/100. "
                "A customer report is not rendered below 60. Close the gaps first."
            ),
        }
    banner = readiness_score < ready_with_assumptions or _has_assumptions(open_items)
    if readiness_score < ready_with_assumptions:
        band = "ready_with_assumptions"
    else:
        band = "ready_to_build"
    return {
        "allowed": True,
        "assumptions_banner": banner,
        "band": band,
        "reason": None,
    }


def _has_assumptions(open_items: list[dict[str, Any]]) -> bool:
    return any(item.get("item_type") == "assumption" for item in open_items)
