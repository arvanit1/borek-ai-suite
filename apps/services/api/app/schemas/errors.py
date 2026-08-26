"""Consistent API error response models (AT-34)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def build_error_response(
    *,
    code: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ErrorResponse(error=ErrorBody(code=code, message=message, detail=detail)).model_dump()
