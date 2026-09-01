"""Runtime execution profile helpers (AT-50 / AT-51)."""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings, settings

logger = logging.getLogger(__name__)

_FIXTURE_WITH_SUPABASE_WARNING = (
    "AI_EXECUTION_MODE=fixture with API_DATA_BACKEND=supabase: Stage A/B use "
    "deterministic fixtures (same plan/slide content every run). Set "
    "AI_EXECUTION_MODE=live in .env for API and worker when testing real transcripts."
)


def runtime_profile(current: Settings | None = None) -> dict[str, str]:
    """Return the active backend execution modes for diagnostics."""
    cfg = current or settings
    return {
        "ai_execution_mode": cfg.AI_EXECUTION_MODE,
        "renderer_execution_mode": cfg.RENDERER_EXECUTION_MODE,
        "api_data_backend": cfg.API_DATA_BACKEND,
    }


def log_runtime_profile(*, component: str, current: Settings | None = None) -> None:
    """Log execution modes at process startup and warn on common misconfiguration."""
    cfg = current or settings
    profile = runtime_profile(cfg)
    logger.info(
        "%s runtime profile: ai_execution_mode=%s renderer_execution_mode=%s api_data_backend=%s",
        component,
        profile["ai_execution_mode"],
        profile["renderer_execution_mode"],
        profile["api_data_backend"],
    )
    if cfg.API_DATA_BACKEND == "supabase" and cfg.AI_EXECUTION_MODE == "fixture":
        logger.warning(_FIXTURE_WITH_SUPABASE_WARNING)


def runtime_warnings(current: Settings | None = None) -> list[str]:
    """Human-readable warnings for /health/runtime and ops checks."""
    cfg = current or settings
    warnings: list[str] = []
    if cfg.API_DATA_BACKEND == "supabase" and cfg.AI_EXECUTION_MODE == "fixture":
        warnings.append(_FIXTURE_WITH_SUPABASE_WARNING)
    if cfg.AI_EXECUTION_MODE == "live" and not cfg.OPENAI_API_KEY.strip():
        warnings.append(
            "AI_EXECUTION_MODE=live but OPENAI_API_KEY is empty: presentation planning will fail."
        )
    return warnings


def runtime_health_payload(current: Settings | None = None) -> dict[str, Any]:
    profile = runtime_profile(current)
    return {
        "status": "ok",
        **profile,
        "warnings": runtime_warnings(current),
    }
