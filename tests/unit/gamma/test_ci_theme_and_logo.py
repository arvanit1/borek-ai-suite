"""CI alignment: official Gamma theme and no deck-wide Borek logo on content slides."""

from __future__ import annotations

import uuid

from app.config import Settings
from services.gamma.live_client import LiveGammaClient
from services.presentation.ci_contract import official_gamma_theme_id
from services.gamma.contract import (
    LOCKED_BOREK_TEMPLATE_ID,
    LOCKED_BOREK_TEMPLATE_VERSION,
    GammaGenerateRequest,
)
from services.gamma.slot_mapping import build_gamma_content_slots

OPPORTUNITY_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def _request(**overrides: object) -> GammaGenerateRequest:
    defaults: dict[str, object] = {
        "template_id": LOCKED_BOREK_TEMPLATE_ID,
        "template_version": LOCKED_BOREK_TEMPLATE_VERSION,
        "opportunity_id": str(OPPORTUNITY_ID),
        "presentation_version_id": "ver-1",
        "output_formats": ("pptx",),
        "slots": build_gamma_content_slots(
            opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        ),
        "timeout_seconds": 30.0,
    }
    return GammaGenerateRequest(**{**defaults, **overrides})  # type: ignore[arg-type]


def test_config_default_matches_official_ci_theme() -> None:
    default = Settings.model_fields["GAMMA_THEME_ID"].default
    assert default == official_gamma_theme_id()


def test_scratch_payload_uses_configured_theme_id() -> None:
    client = LiveGammaClient(api_key="k", theme_id=official_gamma_theme_id())
    payload = client._generation_payload(_request())  # noqa: SLF001
    assert payload["themeId"] == "y7pjh5eetjgbiym"


def test_scratch_payload_without_client_logo_omits_header_footer() -> None:
    client = LiveGammaClient(api_key="k", theme_id=official_gamma_theme_id())
    payload = client._generation_payload(_request())  # noqa: SLF001
    assert "cardOptions" not in payload
    header = (payload.get("cardOptions") or {}).get("headerFooter") or {}
    assert "bottomLeft" not in header


def test_theme_override_still_propagates() -> None:
    override = "custom-theme-override"
    client = LiveGammaClient(api_key="k", theme_id=override)
    payload = client._generation_payload(_request())  # noqa: SLF001
    assert payload["themeId"] == override
