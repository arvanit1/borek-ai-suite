"""Phase 2 Gamma spike: provider contract and deterministic fixture client."""

from __future__ import annotations

from typing import get_args

import pytest

from services.gamma.contract import (
    LOCKED_BOREK_TEMPLATE_ID,
    LOCKED_BOREK_TEMPLATE_VERSION,
    GammaAuthError,
    GammaContentSlot,
    GammaErrorClass,
    GammaGenerateRequest,
    GammaPayloadError,
    GammaProvider,
    GammaProviderError,
    GammaRateLimitError,
    GammaTemplateError,
    GammaTimeoutError,
)
from services.gamma.fixture_client import FixtureGammaClient


def _request(**overrides: object) -> GammaGenerateRequest:
    payload = {
        "template_id": LOCKED_BOREK_TEMPLATE_ID,
        "template_version": LOCKED_BOREK_TEMPLATE_VERSION,
        "opportunity_id": "opp-142",
        "presentation_version_id": "pv-9",
        "output_formats": ("pptx", "pdf"),
        "slots": (
            GammaContentSlot("cover.title", "Invoice 3-way Match"),
            GammaContentSlot("cover.client_name", "Acme Corp"),
        ),
        "client_logo_ref": "artifact:logos/acme.svg",
        "timeout_seconds": 30.0,
    }
    payload.update(overrides)
    return GammaGenerateRequest(**payload)  # type: ignore[arg-type]


def test_fixture_client_satisfies_provider_contract() -> None:
    client: GammaProvider = FixtureGammaClient()
    result = client.generate(_request())
    assert result.template_id == LOCKED_BOREK_TEMPLATE_ID
    assert result.template_version == LOCKED_BOREK_TEMPLATE_VERSION
    assert result.branding_locked is True
    assert result.client_logo_applied is True
    formats = {artifact.format for artifact in result.artifacts}
    assert formats == {"pptx", "pdf"}


def test_payload_shape_accepts_named_content_slots_only() -> None:
    client = FixtureGammaClient()
    with pytest.raises(GammaPayloadError) as exc:
        client.generate(
            _request(slots=(GammaContentSlot("layout.left_rail", "nope"),))
        )
    assert exc.value.classification == "payload"
    assert exc.value.retryable is False


def test_template_and_branding_are_locked() -> None:
    client = FixtureGammaClient()
    with pytest.raises(GammaTemplateError) as wrong_template:
        client.generate(_request(template_id="client-custom-theme"))
    assert wrong_template.value.classification == "template"

    with pytest.raises(GammaTemplateError) as branding:
        client.generate(
            _request(slots=(GammaContentSlot("brand_color", "#ff0000"),))
        )
    assert "locked" in str(branding.value).lower()


def test_client_logo_reference_is_optional() -> None:
    client = FixtureGammaClient()
    without_logo = client.generate(_request(client_logo_ref=None))
    assert without_logo.client_logo_applied is False
    with_logo = client.generate(_request(client_logo_ref="s3://borek-client-logos/acme.png"))
    assert with_logo.client_logo_applied is True
    with pytest.raises(GammaPayloadError):
        client.generate(_request(client_logo_ref="https://evil.example/logo.png"))


def test_artifact_metadata_and_ownership() -> None:
    result = FixtureGammaClient().generate(_request())
    assert len(result.artifacts) == 2
    for artifact in result.artifacts:
        assert artifact.owner_opportunity_id == "opp-142"
        assert artifact.owner_presentation_version_id == "pv-9"
        assert artifact.storage_key.startswith("gamma/opp-142/pv-9/")
        assert artifact.byte_size > 0
        assert len(artifact.checksum_sha256) == 64
        if artifact.format == "pptx":
            assert artifact.content_type.endswith("presentationml.presentation")
            assert artifact.storage_key.endswith(".pptx")
        else:
            assert artifact.content_type == "application/pdf"
            assert artifact.storage_key.endswith(".pdf")


def test_timeout_and_error_classification() -> None:
    timeout = FixtureGammaClient()
    with pytest.raises(GammaTimeoutError) as timed_out:
        timeout.generate(_request(timeout_seconds=0))
    assert timed_out.value.classification == "timeout"
    assert timed_out.value.retryable is True

    cases = [
        ("timeout", GammaTimeoutError, "timeout", True),
        ("auth", GammaAuthError, "auth", False),
        ("rate_limit", GammaRateLimitError, "rate_limit", True),
        ("provider", GammaProviderError, "provider", True),
    ]
    for force, exc_type, classification, retryable in cases:
        client = FixtureGammaClient(force_failure=force)  # type: ignore[arg-type]
        with pytest.raises(exc_type) as exc:
            client.generate(_request())
        assert exc.value.classification == classification
        assert exc.value.retryable is retryable

    assert set(get_args(GammaErrorClass)) == {
        "timeout",
        "auth",
        "template",
        "payload",
        "rate_limit",
        "provider",
    }
