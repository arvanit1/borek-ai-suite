"""Infrastructure health endpoint (AT-34)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — no auth, no database dependency."""
    return {"status": "ok"}
