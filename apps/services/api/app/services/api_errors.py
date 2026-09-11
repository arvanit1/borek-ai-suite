"""Shared API exceptions for data layer routes."""

from __future__ import annotations

from fastapi import HTTPException, status


def error_fields_from_exception(exc: BaseException) -> tuple[str, str, bool]:
    """Return (code, message, retryable) for worker fail_job / continuation."""
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, HTTPException):
            detail = current.detail
            retryable = current.status_code >= 500
            if isinstance(detail, dict):
                code = str(detail.get("code") or "JOB_FAILED")
                message = str(detail.get("message") or "Job failed")
                return code, message, retryable
            return "JOB_FAILED", str(detail or current), retryable
        current = current.__cause__
    code = str(getattr(exc, "code", "") or getattr(exc, "error_code", "") or "JOB_FAILED")
    message = str(exc)
    retryable = bool(getattr(exc, "retryable", False))
    return code, message, retryable


def not_found(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": code, "message": message},
    )


def bad_request(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": code, "message": message},
    )


def forbidden(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": code, "message": message},
    )


def conflict(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": code, "message": message},
    )


def service_unavailable(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": code, "message": message},
    )
