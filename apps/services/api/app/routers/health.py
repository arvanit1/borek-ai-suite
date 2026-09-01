"""Infrastructure health endpoint (AT-34 / AT-50)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.runtime_profile import runtime_health_payload

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — no auth, no database dependency."""
    return {"status": "ok"}


@router.get("/health/runtime")
def health_runtime() -> dict[str, Any]:
    """Expose execution modes so API/worker/docker can be verified without shell access."""
    return runtime_health_payload()
