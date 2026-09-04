"""AT-60: live adapter, factory, artifact storage, retry classification."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from services.gamma.artifacts import persist_gamma_result
from services.gamma.contract import (
    LOCKED_BOREK_TEMPLATE_ID,
    LOCKED_BOREK_TEMPLATE_VERSION,
    GammaAuthError,
    GammaContentSlot,
    GammaGenerateRequest,
    GammaPayloadError,
    GammaProviderError,
    GammaRateLimitError,
    GammaTemplateError,
    GammaTimeoutError,
)
from services.gamma.fixture_client import FixtureGammaClient
from services.gamma.live_client import LiveGammaClient, raise_for_gamma_status
from services.gamma.provider import build_gamma_provider


def _request(**overrides: object) -> GammaGenerateRequest:
    payload = {
        "template_id": LOCKED_BOREK_TEMPLATE_ID,
        "template_version": LOCKED_BOREK_TEMPLATE_VERSION,
        "opportunity_id": "opp-142",
        "presentation_version_id": "pv-9",
        "output_formats": ("pptx",),
        "slots": (GammaContentSlot("cover.title", "Invoice 3-way Match"),),
        "timeout_seconds": 30.0,
    }
    payload.update(overrides)
    return GammaGenerateRequest(**payload)  # type: ignore[arg-type]


class _ScriptedClient:
    def __init__(self, scripted: list[httpx.Response]) -> None:
        self._scripted = list(scripted)
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, **_kwargs: object) -> httpx.Response:
        self.calls.append((method, url))
        return self._scripted.pop(0)

    def get(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def close(self) -> None:
        return None


def _json_response(status: int, payload: dict, url: str = "https://public-api.gamma.app/v1.0/generations") -> httpx.Response:
    return httpx.Response(status, json=payload, request=httpx.Request("GET", url))


def _bytes_response(content: bytes, url: str) -> httpx.Response:
    return httpx.Response(200, content=content, request=httpx.Request("GET", url))


def test_factory_uses_fixture_without_calling_gamma() -> None:
    provider = build_gamma_provider(execution_mode="fixture")
    assert isinstance(provider, FixtureGammaClient)
    result = provider.generate(_request())
    assert result.branding_locked is True
    assert result.artifacts[0].content


def test_live_factory_without_key_fails_closed_on_generate() -> None:
    provider = build_gamma_provider(
        execution_mode="live",
        api_key="",
        theme_id="4kv51cbpy4xonmj",
    )
    with pytest.raises(GammaAuthError) as exc:
        provider.generate(_request())
    assert exc.value.retryable is False


def test_live_client_creates_polls_and_stores_owned_bytes(tmp_path: Path) -> None:
    export_url = "https://exports.example/deck.pptx"
    http = _ScriptedClient(
        [
            _json_response(200, {"generationId": "gen-1"}),
            _json_response(
                200,
                {
                    "status": "completed",
                    "gammaId": "gamma-1",
                    "exportUrl": export_url,
                },
                url="https://public-api.gamma.app/v1.0/generations/gen-1",
            ),
            _bytes_response(b"PPTX-BYTES", export_url),
        ]
    )
    client = LiveGammaClient(
        api_key="sk-gamma-test",
        theme_id="4kv51cbpy4xonmj",
        http_client=http,  # type: ignore[arg-type]
    )
    with patch("services.gamma.live_client.time.sleep"):
        result = persist_gamma_result(client.generate(_request()), artifact_root=tmp_path)
    artifact = result.artifacts[0]
    stored = tmp_path / artifact.storage_key
    assert stored.read_bytes() == b"PPTX-BYTES"
    assert artifact.owner_opportunity_id == "opp-142"
    assert artifact.storage_key.startswith("gamma/opp-142/pv-9/")
    assert artifact.content == b""
    assert any(path.endswith("/v1.0/generations") for _method, path in http.calls)


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, GammaAuthError),
        (403, GammaAuthError),
        (429, GammaRateLimitError),
        (404, GammaTemplateError),
        (422, GammaPayloadError),
        (500, GammaProviderError),
    ],
)
def test_live_status_codes_are_classified(status: int, error_type: type[Exception]) -> None:
    with pytest.raises(error_type):
        raise_for_gamma_status(_json_response(status, {"error": "nope"}))


def test_retry_flags_match_gamma_error_classes() -> None:
    assert GammaTimeoutError().retryable is True
    assert GammaRateLimitError().retryable is True
    assert GammaProviderError().retryable is True
    assert GammaAuthError().retryable is False
    assert GammaTemplateError("locked").retryable is False
    assert GammaPayloadError("bad slot").retryable is False
