"""Select the AT-60 Gamma provider from the execution flag."""

from __future__ import annotations

from typing import Literal

from services.gamma.contract import GammaAuthError, GammaProvider
from services.gamma.fixture_client import FixtureGammaClient
from services.gamma.live_client import LiveGammaClient

GammaExecutionMode = Literal["fixture", "live"]


def build_gamma_provider(
    *,
    execution_mode: GammaExecutionMode,
    api_key: str = "",
    base_url: str = "https://public-api.gamma.app",
    theme_id: str = "",
    template_id: str = "",
    force_failure: str | None = None,
) -> GammaProvider:
    if execution_mode == "fixture":
        return FixtureGammaClient(force_failure=force_failure)  # type: ignore[arg-type]
    if execution_mode != "live":
        raise GammaAuthError(f"Unsupported GAMMA_EXECUTION_MODE '{execution_mode}'.")
    return LiveGammaClient(
        api_key=api_key,
        base_url=base_url,
        theme_id=theme_id,
        template_id=template_id,
    )
