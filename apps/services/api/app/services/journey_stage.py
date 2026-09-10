"""BT-31: cumulative journey-stage eligibility, lineage, and prior-stage context."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.schemas.journey_stage import JOURNEY_STAGES, JourneyStageEligibilityResponse
from app.services.data import DataStore

ENTRY_JOURNEY_STAGE = "first_contact"
COMPLETED_VERSION_STATUS = "ready"
PREREQUISITE_STAGE = {
    "first_contact": None,
    "deepening": "first_contact",
    "concretisation": "deepening",
}
NEXT_ACTION_FOR_MISSING = {
    "first_contact": "complete_first_contact",
    "deepening": "complete_deepening",
}


def resolve_requested_journey_stage(stage: str | None) -> str:
    """Require an explicit stage at the API. Omitted resolves to First contact, never deepening."""
    value = str(stage or "").strip()
    if not value:
        return ENTRY_JOURNEY_STAGE
    if value not in JOURNEY_STAGES:
        raise _eligibility_http_error(
            code="JOURNEY_STAGE_UNKNOWN",
            message=(
                f"Unknown journey stage '{stage}'. "
                f"Expected one of: {', '.join(JOURNEY_STAGES)}."
            ),
            payload={
                "requested_journey_stage": value,
                "startable": False,
                "prerequisite_stage": None,
                "prior_stage_presentation_version_id": None,
                "reason": "JOURNEY_STAGE_UNKNOWN",
                "next_action": "select_journey_stage",
            },
        )
    return value


def evaluate_opportunity_eligibility(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    requested_journey_stage: str | None = None,
) -> dict[str, Any]:
    store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    requested = (
        resolve_requested_journey_stage(requested_journey_stage)
        if requested_journey_stage is not None
        else None
    )
    stages = [
        _evaluate_stage(store, opportunity_id=opportunity_id, user_id=user_id, stage=stage)
        for stage in JOURNEY_STAGES
    ]
    selected = next(
        (row for row in stages if requested is not None and row["journey_stage"] == requested),
        stages[0],
    )
    return {
        "schema_version": "1.0",
        "opportunity_id": opportunity_id,
        "requested_journey_stage": requested,
        "startable": selected["startable"],
        "prerequisite_stage": selected["prerequisite_stage"],
        "prior_stage_presentation_version_id": selected["prior_stage_presentation_version_id"],
        "reason": selected["reason"],
        "next_action": selected["next_action"],
        "stages": stages,
    }


def require_startable_journey_stage(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    journey_stage: str | None,
) -> dict[str, Any]:
    """Refuse a locked stage before any plan or generation job is created."""
    resolved = resolve_requested_journey_stage(journey_stage)
    payload = evaluate_opportunity_eligibility(
        store,
        opportunity_id=opportunity_id,
        user_id=user_id,
        requested_journey_stage=resolved,
    )
    if payload["startable"]:
        return payload
    message = _blocked_message(payload)
    raise _eligibility_http_error(code="INPUT_REQUIRED", message=message, payload=payload)


def find_completed_stage_version(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    journey_stage: str,
) -> dict[str, Any] | None:
    versions = [
        row
        for row in store.list_presentation_versions_for_opportunity(
            opportunity_id=opportunity_id,
            user_id=user_id,
        )
        if str(row.get("journey_stage") or "") == journey_stage
    ]
    completed = [row for row in versions if str(row.get("status") or "") == COMPLETED_VERSION_STATUS]
    if completed:
        return max(completed, key=_version_sort_key)
    return None


def resolve_prior_framework(
    store: DataStore,
    *,
    prior_version: dict[str, Any],
    user_id: UUID,
) -> dict[str, Any]:
    """Prior Framework is the prior presentation version's plan.framework_version_id."""
    try:
        presentation = store.get_presentation(
            presentation_id=_as_uuid(prior_version["presentation_id"]),
            user_id=user_id,
        )
        plan = store.get_presentation_plan(
            presentation_plan_id=_as_uuid(presentation["presentation_plan_id"]),
            user_id=user_id,
        )
        framework = store.get_framework_version(
            framework_version_id=_as_uuid(plan["framework_version_id"]),
            user_id=user_id,
        )
    except HTTPException as exc:
        raise _prior_framework_error(prior_version) from exc
    if str(framework.get("status") or "") != "confirmed":
        raise _prior_framework_error(prior_version)
    return framework


def build_prior_stage_context(
    store: DataStore,
    *,
    opportunity: dict[str, Any],
    prior_version: dict[str, Any],
    user_id: UUID,
) -> dict[str, Any]:
    """JJ-31 prior_stage_context: slots + grounded_facts from the completed prior payload."""
    from services.gamma.payload import build_gamma_content_payload

    framework = resolve_prior_framework(store, prior_version=prior_version, user_id=user_id)
    prior_stage = str(prior_version.get("journey_stage") or "").strip()
    if prior_stage not in JOURNEY_STAGES:
        raise _prior_framework_error(prior_version)
    payload = build_gamma_content_payload(
        opportunity=opportunity,
        framework=framework,
        stage=prior_stage,
    )
    return {
        "slots": list(payload.get("slots") or []),
        "grounded_facts": list(payload.get("grounded_facts") or []),
    }


def load_prior_stage_context_for_version(
    store: DataStore,
    *,
    opportunity: dict[str, Any],
    version: dict[str, Any],
    user_id: UUID,
) -> dict[str, Any] | None:
    prior_id = version.get("prior_stage_presentation_version_id")
    if prior_id is None or prior_id == "":
        return None
    try:
        prior = store.get_presentation_version(
            presentation_version_id=_as_uuid(prior_id),
            user_id=user_id,
        )
    except HTTPException as exc:
        raise superseded_prior_error(
            prior_id,
            requested_stage=str(version.get("journey_stage") or "") or None,
        ) from exc
    if str(prior.get("status") or "") != COMPLETED_VERSION_STATUS:
        raise _eligibility_http_error(
            code="INPUT_REQUIRED",
            message="The prior-stage presentation is no longer completed.",
            payload={
                "requested_journey_stage": version.get("journey_stage"),
                "startable": False,
                "prerequisite_stage": prior.get("journey_stage"),
                "prior_stage_presentation_version_id": str(prior_id),
                "reason": "PREREQUISITE_SUPERSEDED",
                "next_action": "regenerate_prior_stage",
            },
        )
    return build_prior_stage_context(
        store,
        opportunity=opportunity,
        prior_version=prior,
        user_id=user_id,
    )


def eligibility_response(payload: dict[str, Any]) -> JourneyStageEligibilityResponse:
    return JourneyStageEligibilityResponse.model_validate(payload)


def _evaluate_stage(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    stage: str,
) -> dict[str, Any]:
    prerequisite = PREREQUISITE_STAGE[stage]
    if prerequisite is None:
        return {
            "journey_stage": stage,
            "startable": True,
            "prerequisite_stage": None,
            "prior_stage_presentation_version_id": None,
            "reason": None,
            "next_action": None,
        }

    versions = [
        row
        for row in store.list_presentation_versions_for_opportunity(
            opportunity_id=opportunity_id,
            user_id=user_id,
        )
        if str(row.get("journey_stage") or "") == prerequisite
    ]
    completed = [row for row in versions if str(row.get("status") or "") == COMPLETED_VERSION_STATUS]
    incomplete = [row for row in versions if str(row.get("status") or "") != COMPLETED_VERSION_STATUS]
    if not completed:
        reason = "PREREQUISITE_INCOMPLETE" if incomplete else "NO_COMPLETED_PREREQUISITE"
        return {
            "journey_stage": stage,
            "startable": False,
            "prerequisite_stage": prerequisite,
            "prior_stage_presentation_version_id": None,
            "reason": reason,
            "next_action": NEXT_ACTION_FOR_MISSING[prerequisite],
        }

    prior = max(completed, key=_version_sort_key)
    try:
        resolve_prior_framework(store, prior_version=prior, user_id=user_id)
    except HTTPException:
        return {
            "journey_stage": stage,
            "startable": False,
            "prerequisite_stage": prerequisite,
            "prior_stage_presentation_version_id": _id_or_none(prior.get("id")),
            "reason": "PRIOR_FRAMEWORK_UNAVAILABLE",
            "next_action": "regenerate_prior_stage",
        }
    return {
        "journey_stage": stage,
        "startable": True,
        "prerequisite_stage": prerequisite,
        "prior_stage_presentation_version_id": _id_or_none(prior.get("id")),
        "reason": None,
        "next_action": None,
    }


def _blocked_message(payload: dict[str, Any]) -> str:
    reason = payload.get("reason")
    prerequisite = payload.get("prerequisite_stage") or "prior stage"
    if reason == "PRIOR_FRAMEWORK_UNAVAILABLE":
        return (
            "The prior-stage Framework could not be loaded from the completed "
            f"{prerequisite} presentation. Regenerate that stage before continuing."
        )
    if reason == "PREREQUISITE_SUPERSEDED":
        return (
            f"The required {prerequisite} presentation is no longer valid. "
            "Regenerate that stage before continuing."
        )
    if reason == "PREREQUISITE_INCOMPLETE":
        return f"Complete the {prerequisite} presentation before starting this stage."
    return f"A completed {prerequisite} presentation is required before this stage can start."


def _eligibility_http_error(
    *,
    code: str,
    message: str,
    payload: dict[str, Any],
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": code,
            "message": message,
            "detail": {
                "requested_journey_stage": payload.get("requested_journey_stage")
                or payload.get("journey_stage"),
                "startable": bool(payload.get("startable")),
                "prerequisite_stage": payload.get("prerequisite_stage"),
                "prior_stage_presentation_version_id": _stringify(
                    payload.get("prior_stage_presentation_version_id")
                ),
                "reason": payload.get("reason"),
                "next_action": payload.get("next_action"),
            },
        },
    )


def _prior_framework_error(prior_version: dict[str, Any]) -> HTTPException:
    return _eligibility_http_error(
        code="INPUT_REQUIRED",
        message=(
            "The prior-stage Framework could not be loaded from the completed "
            "presentation. Regenerate that stage before continuing."
        ),
        payload={
            "requested_journey_stage": None,
            "startable": False,
            "prerequisite_stage": prior_version.get("journey_stage"),
            "prior_stage_presentation_version_id": prior_version.get("id"),
            "reason": "PRIOR_FRAMEWORK_UNAVAILABLE",
            "next_action": "regenerate_prior_stage",
        },
    )


def _version_sort_key(row: dict[str, Any]) -> tuple:
    created = row.get("created_at") or ""
    version_number = int(row.get("version_number") or 0)
    return (str(created), version_number, str(row.get("id") or ""))


def _as_uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _id_or_none(value: Any) -> UUID | None:
    if value is None or value == "":
        return None
    return _as_uuid(value)


def _stringify(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


# Re-export so callers can raise the same classified shape for a missing version.
def superseded_prior_error(prior_id: Any, *, requested_stage: str | None) -> HTTPException:
    return _eligibility_http_error(
        code="INPUT_REQUIRED",
        message="The required prior-stage presentation no longer exists.",
        payload={
            "requested_journey_stage": requested_stage,
            "startable": False,
            "prerequisite_stage": None,
            "prior_stage_presentation_version_id": prior_id,
            "reason": "PREREQUISITE_SUPERSEDED",
            "next_action": "regenerate_prior_stage",
        },
    )


__all__ = [
    "ENTRY_JOURNEY_STAGE",
    "build_prior_stage_context",
    "eligibility_response",
    "evaluate_opportunity_eligibility",
    "find_completed_stage_version",
    "load_prior_stage_context_for_version",
    "require_startable_journey_stage",
    "resolve_prior_framework",
    "resolve_requested_journey_stage",
    "superseded_prior_error",
]
