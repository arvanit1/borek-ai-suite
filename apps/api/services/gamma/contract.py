"""Gamma provider contract (AT-60).

The locked Borek template id is the Pitch Factory name. The live adapter maps
it onto the workspace theme (and optional Gamma template id when JJ-26 lands).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

GammaOutputFormat = Literal["pptx", "pdf"]
GammaErrorClass = Literal[
    "timeout",
    "auth",
    "template",
    "payload",
    "rate_limit",
    "provider",
]

LOCKED_BOREK_TEMPLATE_ID = "borek-branded-standard"
LOCKED_BOREK_TEMPLATE_VERSION = "v1"
ALLOWED_CONTENT_SLOTS = frozenset(
    {
        "cover.title",
        "cover.client_name",
        "context.summary",
        "scope.in_scope",
        "next_steps.body",
    }
)
FORBIDDEN_BRANDING_KEYS = frozenset(
    {
        "brand_color",
        "theme",
        "font",
        "logo_override",
        "template_css",
        "master_id",
    }
)
VALID_LOGO_PREFIXES = ("artifact:logos/", "s3://borek-client-logos/")


@dataclass(frozen=True)
class GammaContentSlot:
    name: str
    value: str


@dataclass(frozen=True)
class GammaGenerateRequest:
    template_id: str
    template_version: str
    opportunity_id: str
    presentation_version_id: str
    output_formats: tuple[GammaOutputFormat, ...]
    slots: tuple[GammaContentSlot, ...]
    client_logo_ref: str | None = None
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class GammaArtifact:
    format: GammaOutputFormat
    artifact_id: str
    content_type: str
    byte_size: int
    checksum_sha256: str
    storage_key: str
    owner_opportunity_id: str
    owner_presentation_version_id: str
    content: bytes = b""


@dataclass(frozen=True)
class GammaGenerateResult:
    generation_id: str
    template_id: str
    template_version: str
    branding_locked: bool
    client_logo_applied: bool
    artifacts: tuple[GammaArtifact, ...]


class GammaError(Exception):
    """Classified Gamma provider failure. Safe to persist as job error metadata."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        classification: GammaErrorClass,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.classification = classification
        self.retryable = retryable


class GammaTimeoutError(GammaError):
    def __init__(self, message: str = "Gamma generation timed out.") -> None:
        super().__init__(
            message,
            code="GAMMA_TIMEOUT",
            classification="timeout",
            retryable=True,
        )


class GammaAuthError(GammaError):
    def __init__(self, message: str = "Gamma credentials are missing or rejected.") -> None:
        super().__init__(
            message,
            code="GAMMA_AUTH",
            classification="auth",
            retryable=False,
        )


class GammaTemplateError(GammaError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="GAMMA_TEMPLATE_LOCKED",
            classification="template",
            retryable=False,
        )


class GammaPayloadError(GammaError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="GAMMA_PAYLOAD_INVALID",
            classification="payload",
            retryable=False,
        )


class GammaRateLimitError(GammaError):
    def __init__(self, message: str = "Gamma rate limit is unknown without live access.") -> None:
        super().__init__(
            message,
            code="GAMMA_RATE_LIMIT",
            classification="rate_limit",
            retryable=True,
        )


class GammaProviderError(GammaError):
    def __init__(self, message: str = "Gamma provider failed.") -> None:
        super().__init__(
            message,
            code="GAMMA_PROVIDER_FAILED",
            classification="provider",
            retryable=True,
        )


class GammaProvider(Protocol):
    """Outbound adapter. Fixture and live clients both implement this."""

    def generate(self, request: GammaGenerateRequest) -> GammaGenerateResult:
        ...
