"""Global exception handlers — consistent error JSON for every route (AT-34)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.errors import build_error_response
from app.services.renderer_client import RendererClientError

logger = logging.getLogger(__name__)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else f"HTTP_{exc.status_code}"
        message = str(exc.detail) if exc.detail else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_response(code=code, message=message),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            code = str(detail.get("code", f"HTTP_{exc.status_code}"))
            message = str(detail.get("message", "Request failed"))
            structured_detail = detail.get("detail")
            if structured_detail is not None and not isinstance(structured_detail, dict):
                structured_detail = {"value": structured_detail}
        elif isinstance(detail, str):
            code = f"HTTP_{exc.status_code}"
            message = detail
            structured_detail = None
        else:
            code = f"HTTP_{exc.status_code}"
            message = "Request failed"
            structured_detail = None

        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_response(code=code, message=message, detail=structured_detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=build_error_response(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                detail={"errors": _jsonable(exc.errors())},
            ),
        )

    @app.exception_handler(RendererClientError)
    async def renderer_client_error_handler(
        _request: Request,
        exc: RendererClientError,
    ) -> JSONResponse:
        status_code = 503 if exc.retryable else 422
        return JSONResponse(
            status_code=status_code,
            content=build_error_response(code=exc.code, message=str(exc)),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=build_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
            ),
        )
