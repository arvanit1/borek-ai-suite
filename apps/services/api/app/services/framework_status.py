"""Framework review-status guards (AT-41 / spec §6.3)."""

from __future__ import annotations

from app.services.api_errors import bad_request, conflict

REVIEWABLE_FRAMEWORK_STATUSES = frozenset({"draft", "in_review"})


def require_reviewable_framework(status: str, *, action: str) -> None:
    if status == "confirmed":
        if action == "confirm":
            raise conflict(
                "FRAMEWORK_ALREADY_CONFIRMED",
                "Framework version is already confirmed",
            )
        raise conflict("FRAMEWORK_IMMUTABLE", "Confirmed framework versions cannot be edited")
    if status in REVIEWABLE_FRAMEWORK_STATUSES:
        return
    if action == "confirm":
        raise bad_request(
            "FRAMEWORK_NOT_CONFIRMABLE",
            f"Framework version status {status} cannot be confirmed",
        )
    if action == "regenerate":
        raise bad_request(
            "FRAMEWORK_NOT_EDITABLE",
            "Only draft or in-review framework versions support chapter regeneration",
        )
    raise bad_request(
        "FRAMEWORK_NOT_EDITABLE",
        f"Framework version status {status} cannot be edited",
    )
