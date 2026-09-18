"""JJ-27/JJ-29: route logo-enabled stages through supported Gamma generation paths."""

from __future__ import annotations

import httpx
import pytest

from services.gamma.client_logo import (
    FALLBACK_WORDMARK,
    REASON_PROVIDER_MODE_NO_LOGO,
    decide_client_logo,
)
from services.gamma import live_client
from services.gamma.contract import GammaPayloadError
from services.gamma.live_client import (
    LiveGammaClient,
    _gamma_image_size_for_max_height_pct,
    client_logo_sent_in_outbound_payload,
    raise_for_gamma_status,
    uses_scratch_generation,
)
from tests.unit.gamma.test_jj27_client_logo_placement import (
    OPPORTUNITY_ID,
    _logo,
    _request,
)
from tests.unit.gamma.test_jj29_signed_logo_url import OWNED_BASE, _mint


def _signed_logo_ref(monkeypatch: pytest.MonkeyPatch) -> str:
    from app.config import settings

    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", OWNED_BASE)
    monkeypatch.setattr(settings, "CLIENT_LOGO_SIGNING_SECRET", "jj29-logo-signing-secret")
    signed = _mint()
    assert signed is not None
    monkeypatch.setattr(
        live_client,
        "owned_https_prefixes",
        lambda: (f"{OWNED_BASE}/",),
    )
    return signed


def test_first_contact_from_template_omits_logo_from_outbound_payload() -> None:
    client = LiveGammaClient(api_key="k", theme_id="theme-1", template_id="tpl-1")
    request = _request()
    payload = client._generation_payload(request)  # noqa: SLF001

    assert client._generation_path(request) == "/v1.0/generations/from-template"  # noqa: SLF001
    assert "gammaId" in payload
    assert "cardOptions" not in payload
    assert client_logo_sent_in_outbound_payload(payload) is False


def test_deepening_fetchable_logo_routes_to_standard_generations(monkeypatch) -> None:
    signed = _signed_logo_ref(monkeypatch)
    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)
    client = LiveGammaClient(api_key="k", theme_id="theme-1", template_id="tpl-1")
    request = _request(client_logo_ref=signed, client_logo_placement=decision.placement)

    assert uses_scratch_generation(request) is True
    assert client._generation_path(request) == "/v1.0/generations"  # noqa: SLF001
    payload = client._generation_payload(request)  # noqa: SLF001
    assert "gammaId" not in payload
    assert payload["textMode"] == "preserve"
    footer = payload["cardOptions"]["headerFooter"]
    bottom_right = footer["bottomRight"]
    assert bottom_right == {
        "type": "image",
        "source": "custom",
        "src": signed,
        "size": "sm",
    }
    assert client_logo_sent_in_outbound_payload(payload) is True


def test_concretisation_fetchable_logo_routes_to_standard_generations(monkeypatch) -> None:
    signed = _signed_logo_ref(monkeypatch)
    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)
    client = LiveGammaClient(api_key="k", theme_id="theme-1", template_id="tpl-1")
    request = _request(client_logo_ref=signed, client_logo_placement=decision.placement)

    assert client._generation_path(request) == "/v1.0/generations"  # noqa: SLF001
    assert client_logo_sent_in_outbound_payload(client._generation_payload(request))  # noqa: SLF001


def test_from_template_payload_never_marks_logo_applied_without_footer_field() -> None:
    client = LiveGammaClient(api_key="k", theme_id="theme-1", template_id="tpl-1")
    payload = client._generation_payload(_request())  # noqa: SLF001
    assert client_logo_sent_in_outbound_payload(payload) is False


def test_stage_metadata_downgrades_when_fetchable_logo_not_in_outbound_payload(
    monkeypatch,
    tmp_path,
) -> None:
    from app.services.gamma_stage import _client_logo_metadata

    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)
    metadata = _client_logo_metadata(
        decision,
        provider_applied=False,
        had_fetchable_logo=True,
    )
    assert metadata["applied"] is False
    assert metadata["reason"] == REASON_PROVIDER_MODE_NO_LOGO
    assert metadata["fallback"] == FALLBACK_WORDMARK


class _ScriptedClient:
    def __init__(self, scripted: list[httpx.Response]) -> None:
        self._scripted = list(scripted)
        self.calls: list[tuple[str, str]] = []
        self.json_bodies: list[object] = []

    def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        self.calls.append((method, url))
        self.json_bodies.append(kwargs.get("json"))
        return self._scripted.pop(0)

    def get(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def close(self) -> None:
        return None


def _json_response(status: int, payload: dict, url: str = "https://public-api.gamma.app/v1.0/generations") -> httpx.Response:
    return httpx.Response(status, json=payload, request=httpx.Request("POST", url))


def test_scratch_payload_uses_gamma_custom_image_schema_without_unsupported_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signed = _signed_logo_ref(monkeypatch)
    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)
    client = LiveGammaClient(api_key="k", theme_id="theme-1", template_id="tpl-1")
    payload = client._generation_payload(  # noqa: SLF001
        _request(client_logo_ref=signed, client_logo_placement=decision.placement),
    )

    assert set(payload) <= {
        "inputText",
        "textMode",
        "format",
        "themeId",
        "exportAs",
        "title",
        "cardSplit",
        "numCards",
        "additionalInstructions",
        "cardOptions",
    }
    bottom_right = payload["cardOptions"]["headerFooter"]["bottomRight"]
    assert set(bottom_right) == {"type", "source", "src", "size"}
    assert "maxHeightPercent" not in bottom_right


def test_jj27_max_height_pct_maps_to_gamma_size_sm() -> None:
    assert _gamma_image_size_for_max_height_pct(6.0) == "sm"


def test_raise_for_gamma_status_surfaces_sanitized_provider_message() -> None:
    response = httpx.Response(
        400,
        json={
            "message": (
                "Input validation errors: 1. cardOptions.headerFooter.bottomRight.source "
                "must be one of the following values: https://secret.example/logo?token=abc"
            ),
            "statusCode": 400,
        },
        request=httpx.Request("POST", "https://public-api.gamma.app/v1.0/generations"),
    )

    with pytest.raises(GammaPayloadError, match="headerFooter.bottomRight.source") as exc:
        raise_for_gamma_status(response)

    assert "https://" not in str(exc.value)
    assert "token=abc" not in str(exc.value)


def test_live_http_post_includes_logo_in_json_body(monkeypatch) -> None:
    signed = _signed_logo_ref(monkeypatch)
    decision = decide_client_logo(_logo(), opportunity_id=OPPORTUNITY_ID)
    export_url = "https://exports.example/deck.pptx"
    http = _ScriptedClient(
        [
            _json_response(200, {"generationId": "gen-1"}),
            _json_response(
                200,
                {"status": "completed", "gammaId": "gamma-1", "exportUrl": export_url},
                url="https://public-api.gamma.app/v1.0/generations/gen-1",
            ),
            httpx.Response(200, content=b"PPTX", request=httpx.Request("GET", export_url)),
        ]
    )
    client = LiveGammaClient(
        api_key="sk-gamma-test",
        theme_id="theme-1",
        template_id="tpl-1",
        http_client=http,  # type: ignore[arg-type]
    )
    request = _request(client_logo_ref=signed, client_logo_placement=decision.placement)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("services.gamma.live_client.time.sleep", lambda *_args: None)
        result = client.generate(request)

    post_url = http.calls[0][1]
    assert post_url.endswith("/v1.0/generations")
    assert not post_url.endswith("/from-template")
    body = http.json_bodies[0]
    assert isinstance(body, dict)
    assert client_logo_sent_in_outbound_payload(body)
    assert body["cardOptions"]["headerFooter"]["bottomRight"] == {
        "type": "image",
        "source": "custom",
        "src": signed,
        "size": "sm",
    }
    assert signed not in str(result)
    assert result.client_logo_applied is True
