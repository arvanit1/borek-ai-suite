"""Deterministic Gamma fixture client. Not a live API client."""

from __future__ import annotations

import hashlib
from typing import Literal
from uuid import uuid5, NAMESPACE_URL

from services.gamma.contract import (
    ALLOWED_CONTENT_SLOTS,
    FORBIDDEN_BRANDING_KEYS,
    LOCKED_BOREK_TEMPLATE_ID,
    LOCKED_BOREK_TEMPLATE_VERSION,
    VALID_LOGO_PREFIXES,
    GammaArtifact,
    GammaAuthError,
    GammaError,
    GammaGenerateRequest,
    GammaGenerateResult,
    GammaPayloadError,
    GammaProviderError,
    GammaRateLimitError,
    GammaTemplateError,
    GammaTimeoutError,
)

FixtureFailure = Literal["timeout", "auth", "rate_limit", "provider"]

_CONTENT_TYPES = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
}
_FIXTURE_SIZES = {"pptx": 4096, "pdf": 2048}


def validate_generate_request(request: GammaGenerateRequest) -> None:
    if request.template_id != LOCKED_BOREK_TEMPLATE_ID:
        raise GammaTemplateError(
            "Only the locked Borek-branded Gamma template may be used; "
            f"got '{request.template_id}'."
        )
    if request.template_version != LOCKED_BOREK_TEMPLATE_VERSION:
        raise GammaTemplateError(
            "The Borek Gamma template version is locked; "
            f"got '{request.template_version}'."
        )
    if not request.opportunity_id or not request.presentation_version_id:
        raise GammaPayloadError("opportunity_id and presentation_version_id are required.")
    if not request.output_formats:
        raise GammaPayloadError("At least one output format is required.")
    unknown_formats = [item for item in request.output_formats if item not in _CONTENT_TYPES]
    if unknown_formats:
        raise GammaPayloadError(f"Unsupported output formats: {unknown_formats}.")
    if len(set(request.output_formats)) != len(request.output_formats):
        raise GammaPayloadError("output_formats must be unique.")
    if not request.slots:
        raise GammaPayloadError("At least one content slot is required.")

    seen: set[str] = set()
    for slot in request.slots:
        if slot.name in FORBIDDEN_BRANDING_KEYS or slot.name.startswith("brand."):
            raise GammaTemplateError(
                f"Slot '{slot.name}' is branding and is locked in the Gamma template."
            )
        if slot.name not in ALLOWED_CONTENT_SLOTS:
            raise GammaPayloadError(f"Slot '{slot.name}' is not a named content slot.")
        if slot.name in seen:
            raise GammaPayloadError(f"Duplicate slot '{slot.name}'.")
        if not slot.value.strip():
            raise GammaPayloadError(f"Slot '{slot.name}' must have content.")
        seen.add(slot.name)

    if request.client_logo_ref is not None:
        if not request.client_logo_ref.startswith(VALID_LOGO_PREFIXES):
            raise GammaPayloadError(
                "client_logo_ref must be an owned storage reference "
                f"starting with {VALID_LOGO_PREFIXES}."
            )

    if request.timeout_seconds <= 0:
        raise GammaTimeoutError()


class FixtureGammaClient:
    """Proves contract behavior without calling Gamma."""

    def __init__(self, *, force_failure: FixtureFailure | None = None) -> None:
        self._force_failure = force_failure

    def generate(self, request: GammaGenerateRequest) -> GammaGenerateResult:
        validate_generate_request(request)
        if self._force_failure:
            raise _forced_error(self._force_failure)

        generation_id = str(
            uuid5(
                NAMESPACE_URL,
                f"gamma-fixture:{request.opportunity_id}:{request.presentation_version_id}",
            )
        )
        artifacts = tuple(
            _artifact(request, output_format=output_format, generation_id=generation_id)
            for output_format in request.output_formats
        )
        return GammaGenerateResult(
            generation_id=generation_id,
            template_id=request.template_id,
            template_version=request.template_version,
            branding_locked=True,
            client_logo_applied=request.client_logo_ref is not None,
            artifacts=artifacts,
        )


def _forced_error(kind: FixtureFailure) -> GammaError:
    mapping: dict[FixtureFailure, GammaError] = {
        "timeout": GammaTimeoutError(),
        "auth": GammaAuthError(),
        "rate_limit": GammaRateLimitError(),
        "provider": GammaProviderError(),
    }
    return mapping[kind]


def _artifact(
    request: GammaGenerateRequest,
    *,
    output_format: str,
    generation_id: str,
) -> GammaArtifact:
    storage_key = (
        f"gamma/{request.opportunity_id}/{request.presentation_version_id}/"
        f"{generation_id}.{output_format}"
    )
    digest = hashlib.sha256(
        f"{storage_key}:{output_format}:{request.template_version}".encode("utf-8")
    ).hexdigest()
    return GammaArtifact(
        format=output_format,  # type: ignore[arg-type]
        artifact_id=f"{generation_id}:{output_format}",
        content_type=_CONTENT_TYPES[output_format],
        byte_size=_FIXTURE_SIZES[output_format],
        checksum_sha256=digest,
        storage_key=storage_key,
        owner_opportunity_id=request.opportunity_id,
        owner_presentation_version_id=request.presentation_version_id,
        content=f"gamma-fixture:{output_format}:{generation_id}".encode("utf-8").ljust(
            _FIXTURE_SIZES[output_format],
            b"\x00",
        ),
    )
