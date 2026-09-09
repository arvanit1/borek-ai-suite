"""JJ-29: a quality-gated logo reaches Gamma only via a short-lived owned HTTPS URL."""

from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlparse

import pytest

from services.gamma.client_logo import FALLBACK_WORDMARK, REASON_APPLIED, decide_client_logo
from services.gamma.contract import gamma_egress_reference
from services.gamma.live_client import LiveGammaClient
from services.gamma.signed_logo import (
    SIGNED_LOGO_PATH,
    mint_signed_client_logo_url,
    owned_https_prefixes,
    verify_signed_client_logo_request,
)

from tests.unit.gamma.test_jj27_client_logo_placement import (
    OPPORTUNITY_ID,
    USER_ID,
    _logo,
    _opportunity,
    _request,
    _run_stage,
)

OWNED_BASE = "https://api.borek.test"
SECRET = "jj29-logo-signing-secret"


def _mint(**overrides: object) -> str | None:
    defaults: dict[str, object] = {
        "opportunity_id": OPPORTUNITY_ID,
        "public_api_base_url": OWNED_BASE,
        "secret": SECRET,
        "ttl_seconds": 900,
        "now": 1_700_000_000,
    }
    return mint_signed_client_logo_url(**{**defaults, **overrides})  # type: ignore[arg-type]


def test_a_signed_url_is_minted_only_on_an_owned_https_host() -> None:
    url = _mint()
    assert url is not None
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "api.borek.test"
    assert parsed.path == f"{SIGNED_LOGO_PATH}{OPPORTUNITY_ID}"
    query = parse_qs(parsed.query)
    assert query["exp"] == ["1700000900"]
    assert query["sig"]
    assert verify_signed_client_logo_request(
        OPPORTUNITY_ID,
        exp=query["exp"][0],
        signature=query["sig"][0],
        secret=SECRET,
        now=1_700_000_000,
    )


@pytest.mark.parametrize("base", ["", "http://api.borek.test", "ftp://api.borek.test"])
def test_http_and_empty_bases_cannot_be_minted(base: str) -> None:
    assert _mint(public_api_base_url=base) is None


def test_empty_secret_cannot_be_minted() -> None:
    assert _mint(secret="") is None


def test_expired_or_tampered_tokens_are_rejected() -> None:
    url = _mint()
    assert url is not None
    query = parse_qs(urlparse(url).query)
    assert (
        verify_signed_client_logo_request(
            OPPORTUNITY_ID,
            exp=query["exp"][0],
            signature=query["sig"][0],
            secret=SECRET,
            now=1_700_000_901,
        )
        is False
    )
    assert (
        verify_signed_client_logo_request(
            OPPORTUNITY_ID,
            exp=query["exp"][0],
            signature="ab" * 32,
            secret=SECRET,
            now=1_700_000_000,
        )
        is False
    )
    assert (
        verify_signed_client_logo_request(
            uuid.uuid4(),
            exp=query["exp"][0],
            signature=query["sig"][0],
            secret=SECRET,
            now=1_700_000_000,
        )
        is False
    )


def test_arbitrary_https_is_still_rejected_when_the_owned_host_is_configured(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", OWNED_BASE)
    signed = _mint()
    assert gamma_egress_reference(signed) == signed
    assert gamma_egress_reference("https://evil.example/logo.png") is None
    assert gamma_egress_reference(f"artifact:logos/{OPPORTUNITY_ID}") is None
    assert any(prefix.startswith(OWNED_BASE) for prefix in owned_https_prefixes())


def test_stage_sends_the_signed_url_instead_of_the_private_ref(monkeypatch, tmp_path) -> None:
    from app.config import settings
    from app.services.data.memory_store import get_memory_store
    from app.services.gamma_stage import build_gamma_request

    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    monkeypatch.setattr(settings, "GAMMA_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", OWNED_BASE)
    monkeypatch.setattr(settings, "CLIENT_LOGO_SIGNING_SECRET", SECRET)
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

    request, logo = build_gamma_request(
        opportunity=opportunity,
        presentation_version_id=uuid.uuid4(),
        user_id=USER_ID,
        store=store,
    )

    assert logo.applied is True
    assert logo.reason == REASON_APPLIED
    assert request.client_logo_ref is not None
    assert request.client_logo_ref.startswith(f"{OWNED_BASE}{SIGNED_LOGO_PATH}")
    assert "artifact:" not in request.client_logo_ref
    assert request.client_logo_placement is not None
    assert request.client_logo_placement.position == "bottom_right"
    assert request.client_logo_placement.cards == ("cover", "closing")

    result = _run_stage(store, opportunity)
    assert result["client_logo"]["applied"] is True
    assert result["client_logo"]["reason"] == REASON_APPLIED
    assert result["client_logo"]["position"] == "bottom_right"
    assert result["client_logo"]["cards"] == ["cover", "closing"]


def test_unsignable_logo_falls_back_to_the_wordmark(monkeypatch, tmp_path) -> None:
    from app.config import settings
    from app.services.data.memory_store import get_memory_store
    from app.services.gamma_stage import build_gamma_request

    monkeypatch.setattr(settings, "PRESENTATION_ENGINE", "gamma")
    monkeypatch.setattr(settings, "GAMMA_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", "")
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

    request, logo = build_gamma_request(
        opportunity=opportunity,
        presentation_version_id=uuid.uuid4(),
        user_id=USER_ID,
        store=store,
    )
    assert logo.applied is True
    assert request.client_logo_ref is None
    assert request.client_logo_placement is None

    result = _run_stage(store, opportunity)
    assert result["client_logo"]["applied"] is False
    assert result["client_logo"]["reason"] == "provider_could_not_fetch_reference"
    assert result["client_logo"]["fallback"] == FALLBACK_WORDMARK


def test_live_payload_places_the_signed_url_bottom_right_and_keeps_borek_left(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", OWNED_BASE)
    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)
    signed = _mint()
    client = LiveGammaClient(api_key="k", theme_id="theme-1")
    payload = client._generation_payload(  # noqa: SLF001
        _request(client_logo_ref=signed, client_logo_placement=decision.placement),
    )
    footer = payload["cardOptions"]["headerFooter"]
    assert footer["bottomLeft"]["source"] == "themeLogo"
    assert footer["bottomRight"]["source"] == signed
    assert footer["bottomRight"]["maxHeightPercent"] == 6.0


def test_live_payload_omits_a_private_reference_even_when_the_gate_passed() -> None:
    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)
    client = LiveGammaClient(api_key="k", theme_id="theme-1")
    payload = client._generation_payload(  # noqa: SLF001
        _request(client_logo_ref=decision.reference, client_logo_placement=decision.placement),
    )
    assert "bottomRight" not in payload["cardOptions"]["headerFooter"]
    assert payload["cardOptions"]["headerFooter"]["bottomLeft"]["source"] == "themeLogo"
