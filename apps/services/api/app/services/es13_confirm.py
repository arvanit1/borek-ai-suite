"""Wire ES-13 pre-confirm validation into the production API path (AT-41 / ES-13)."""

from __future__ import annotations

import copy
from typing import Any

from fastapi import HTTPException, status

from services.framework.pre_confirm_check import PreConfirmError, pre_confirm_check


def apply_es13_confirm_gate(framework_json: dict[str, Any]) -> dict[str, Any]:
    """Run the ES-13 gate without changing any reviewed Framework content."""
    try:
        checked = copy.deepcopy(framework_json)
        pre_confirm_check(checked)
        return checked
    except PreConfirmError as exc:
        raise pre_confirm_failed(exc.user_message) from exc


def pre_confirm_failed(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"code": "PRE_CONFIRM_FAILED", "message": message},
    )
