"""JJ-27: where a client logo appears, and what happens when it cannot."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest

from services.gamma import live_client

from services.gamma.client_logo import (
    FALLBACK_WORDMARK,
    REASON_APPLIED,
    REASON_APPLIED_ON_PLATE,
    REASON_BELOW_MIN_EDGE,
    REASON_DIMENSIONS_UNKNOWN,
    REASON_EXTREME_ASPECT_RATIO,
    REASON_MISSING,
    ClientLogoPlacement,
    decide_client_logo,
)
from services.gamma.contract import (
    LOCKED_BOREK_TEMPLATE_ID,
    LOCKED_BOREK_TEMPLATE_VERSION,
    GammaGenerateRequest,
    GammaPayloadError,
    GammaTemplateError,
)
from services.gamma.fixture_client import FixtureGammaClient, validate_generate_request
from services.gamma.live_client import LiveGammaClient
from services.gamma.slot_mapping import build_gamma_content_slots
from services.gamma.template import load_gamma_template

OPPORTUNITY_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _logo(**overrides: object) -> dict[str, object]:
    return {
        "mime_type": "image/png",
        "width_px": 512,
        "height_px": 256,
        **overrides,
    }


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


def test_a_good_logo_is_co_branded_bottom_right_on_cover_and_closing() -> None:
    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)

    assert decision.applied is True
    assert decision.reason == REASON_APPLIED
    assert decision.reference == f"artifact:logos/{OPPORTUNITY_ID}"
    placement = decision.placement
    assert placement is not None
    assert placement.position == "bottom_right"
    assert placement.cards == ("cover", "closing")
    assert placement.co_brand_with_borek_logo is True
    assert placement.backdrop == "none"
    assert placement.max_height_pct == 6.0


def test_a_logo_without_transparency_gets_a_white_plate() -> None:
    decision = decide_client_logo(
        _logo(mime_type="image/jpeg"),
        opportunity_id=OPPORTUNITY_ID,
    )
    assert decision.applied is True
    assert decision.reason == REASON_APPLIED_ON_PLATE
    assert decision.placement is not None
    assert decision.placement.backdrop == "white_plate"


@pytest.mark.parametrize(
    ("metadata", "reason"),
    [
        (None, REASON_MISSING),
        ({}, REASON_MISSING),
        (_logo(width_px=None, height_px=None), REASON_DIMENSIONS_UNKNOWN),
        (_logo(width_px=96, height_px=96), REASON_BELOW_MIN_EDGE),
        (_logo(width_px=2048, height_px=128), REASON_EXTREME_ASPECT_RATIO),
    ],
)
def test_a_missing_or_poor_logo_falls_back_to_the_client_name_wordmark(
    metadata: dict[str, object] | None,
    reason: str,
) -> None:
    decision = decide_client_logo(metadata, opportunity_id=OPPORTUNITY_ID)

    assert decision.applied is False
    assert decision.reason == reason
    assert decision.fallback == FALLBACK_WORDMARK
    assert decision.reference is None
    assert decision.placement is None
    assert decision.detail


def test_the_wordmark_fallback_always_has_a_client_name_to_use() -> None:
    """The fallback is only meaningful because cover.client_name is required."""
    assert load_gamma_template().slot("cover.client_name").required is True


def test_the_placement_gate_is_stricter_than_the_upload_gate() -> None:
    """AT-58 accepts 64px; too coarse to sit beside the Borek wordmark."""
    from app.services.client_logos import MIN_CLIENT_LOGO_EDGE_PX

    assert load_gamma_template().client_logo.min_edge_px > MIN_CLIENT_LOGO_EDGE_PX


def test_decision_metadata_is_job_safe() -> None:
    metadata = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID).as_metadata()
    assert metadata["applied"] is True
    assert metadata["position"] == "bottom_right"
    serialized = repr(metadata)
    assert "artifact:" not in serialized
    assert "storage_path" not in serialized


def test_a_reference_without_a_placement_takes_the_locked_default() -> None:
    """Omitting the placement is not a way to choose a different one."""
    validate_generate_request(_request(client_logo_ref=f"artifact:logos/{OPPORTUNITY_ID}"))


def test_a_placement_without_a_reference_is_rejected() -> None:
    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)
    with pytest.raises(GammaPayloadError, match="requires a client_logo_ref"):
        validate_generate_request(_request(client_logo_placement=decision.placement))


@pytest.mark.parametrize(
    "placement",
    [
        ClientLogoPlacement(("cover",), "top_left", 6.0, 3.0, True, "none"),
        ClientLogoPlacement(("context",), "bottom_right", 6.0, 3.0, True, "none"),
        ClientLogoPlacement(("cover",), "bottom_right", 40.0, 3.0, True, "none"),
    ],
)
def test_the_template_refuses_placements_outside_the_co_branding_area(
    placement: ClientLogoPlacement,
) -> None:
    with pytest.raises(GammaTemplateError):
        validate_generate_request(
            _request(
                client_logo_ref=f"artifact:logos/{OPPORTUNITY_ID}",
                client_logo_placement=placement,
            ),
        )


def test_the_fixture_provider_reports_an_applied_logo() -> None:
    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)
    result = FixtureGammaClient().generate(
        _request(
            client_logo_ref=decision.reference,
            client_logo_placement=decision.placement,
        ),
    )
    assert result.client_logo_applied is True


def test_a_private_reference_is_left_out_of_the_live_payload() -> None:
    """Gamma cannot fetch `artifact:`, so the deck must not ask it to try."""
    client = LiveGammaClient(api_key="k", theme_id="theme-1")
    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)

    payload = client._generation_payload(  # noqa: SLF001 - payload shape is the contract
        _request(
            client_logo_ref=decision.reference,
            client_logo_placement=decision.placement,
        ),
    )
    assert "bottomRight" not in payload["cardOptions"]["headerFooter"]
    assert payload["cardOptions"]["headerFooter"]["bottomLeft"]["source"] == "themeLogo"


def test_a_signed_url_from_an_owned_host_is_placed_bottom_right(monkeypatch) -> None:
    signed_url = "https://logos.borek.example/acme.png?sig=abc"
    template = load_gamma_template()
    owned = replace(template, client_logo=replace(
        template.client_logo,
        signed_url_prefixes=("https://logos.borek.example/",),
    ))
    monkeypatch.setattr(live_client, "load_gamma_template", lambda: owned)

    client = LiveGammaClient(api_key="k", theme_id="theme-1")
    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)
    payload = client._generation_payload(  # noqa: SLF001
        _request(client_logo_ref=signed_url, client_logo_placement=decision.placement),
    )

    bottom_right = payload["cardOptions"]["headerFooter"]["bottomRight"]
    assert bottom_right["source"] == signed_url
    assert bottom_right["maxHeightPercent"] == 6.0
    # The Borek logo keeps its own corner.
    assert payload["cardOptions"]["headerFooter"]["bottomLeft"]["source"] == "themeLogo"


def test_an_arbitrary_external_url_is_never_an_accepted_reference() -> None:
    with pytest.raises(GammaPayloadError, match="owned storage reference"):
        validate_generate_request(_request(client_logo_ref="https://evil.example/logo.png"))


def _run_stage(store, opportunity) -> dict:
    from app.services.gamma_stage import run_gamma_rendering_stage

    return run_gamma_rendering_stage(
        store,
        job_id=uuid.uuid4(),
        opportunity=opportunity,
        presentation_version_id=uuid.uuid4(),
        user_id=USER_ID,
    )


def _opportunity(store):
    return store.create_opportunity(
        user_id=USER_ID,
        client_name="Acme",
        opportunity_name="Invoice 3-way Match",
        department="Finance",
        language="en",
        pii_redaction_enabled=True,
        additional_client_information=None,
    )


def test_the_stage_records_why_a_deck_has_no_client_mark(monkeypatch, tmp_path) -> None:
    from app.config import settings
    from app.services.data.memory_store import get_memory_store

    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    monkeypatch.setattr(settings, "GAMMA_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    store = get_memory_store()

    result = _run_stage(store, _opportunity(store))

    assert result["client_logo"] == {
        "applied": False,
        "reason": REASON_MISSING,
        "detail": "No client logo is stored for this opportunity.",
        "fallback": FALLBACK_WORDMARK,
        "position": None,
        "cards": [],
        "backdrop": None,
    }


def test_the_stage_reports_a_placed_logo_from_the_stored_upload(monkeypatch, tmp_path) -> None:
    from app.config import settings
    from app.services.data.memory_store import get_memory_store

    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    monkeypatch.setattr(settings, "GAMMA_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    store = get_memory_store()
    opportunity = _opportunity(store)
    store.upsert_client_logo(
        opportunity_id=opportunity["id"],
        user_id=USER_ID,
        file_name="acme.png",
        mime_type="image/png",
        size_bytes=1024,
        storage_path=f"{opportunity['id']}/client-logo/acme.png",
        content=b"\x89PNG\r\n\x1a\n",
        width_px=512,
        height_px=256,
    )

    logo = _run_stage(store, opportunity)["client_logo"]

    assert logo["applied"] is True
    assert logo["reason"] == REASON_APPLIED
    assert logo["position"] == "bottom_right"
    assert logo["cards"] == ["cover", "closing"]
