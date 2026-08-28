"""Wire ES-13 pre-confirm validation into the production API path (AT-41 / ES-13)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from services.framework.pre_confirm_check import PreConfirmError, confirm_customer_report


def apply_es13_confirm_gate(framework_json: dict[str, Any]) -> dict[str, Any]:
    """Run ES-13 (+ ES-30 confirm readiness) and return confirmed framework JSON."""
    try:
        return confirm_customer_report(framework_json)
    except PreConfirmError as exc:
        raise pre_confirm_failed(exc.user_message) from exc


def pre_confirm_failed(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"code": "PRE_CONFIRM_FAILED", "message": message},
    )
