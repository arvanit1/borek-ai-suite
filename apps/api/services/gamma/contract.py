"""Gamma provider contract (AT-60).

The locked Borek template id is the Pitch Factory name. The live adapter maps
it onto the workspace theme and the Gamma template id. Template identity and
the named content slots come from the JJ-26 contract in
`packages/contracts/gamma_template.json`.

Public error codes, retryability, and the owned-host reference rule are frozen
in `packages/contracts/gamma_provider.json` (AT-60A).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Protocol

from services.gamma.client_logo import ClientLogoPlacement
from services.gamma.signed_logo import owned_https_prefixes as configured_owned_https_prefixes
from services.gamma.template import load_gamma_template

GammaOutputFormat = Literal["pptx", "pdf"]
GammaErrorClass = Literal[
    "timeout",
    "auth",
    "template",
    "payload",
    "rate_limit",
    "provider",
]

_PROVIDER_PATH = (
    Path(__file__).resolve().parents[4] / "packages" / "contracts" / "gamma_provider.json"
)
_ALLOWED_ERROR_CLASSES = frozenset(
    ("timeout", "auth", "template", "payload", "rate_limit", "provider")
)

_TEMPLATE = load_gamma_template()

LOCKED_BOREK_TEMPLATE_ID = _TEMPLATE.template_id
LOCKED_BOREK_TEMPLATE_VERSION = _TEMPLATE.template_version
ALLOWED_CONTENT_SLOTS = frozenset(_TEMPLATE.slot_names)
FORBIDDEN_BRANDING_KEYS = _TEMPLATE.locked_keys


class GammaProviderContractError(RuntimeError):
    """The AT-60A provider contract on disk is unusable."""


@dataclass(frozen=True)
class GammaPublicErrorSpec:
    code: str
    classification: GammaErrorClass
    retryable: bool


@dataclass(frozen=True)
class GammaReferencePolicy:
    never_egress_schemes: tuple[str, ...]
    accepted_private_prefixes: tuple[str, ...]
    owned_https_prefixes_from: str
    empty_owned_https_prefixes_valid: bool
    egress_requires_https: bool
    arbitrary_https_not_trusted: bool
    unfetchable_fallback: str


@dataclass(frozen=True)
class GammaProviderContract:
    schema_version: str
    errors: tuple[GammaPublicErrorSpec, ...]
    reference_policy: GammaReferencePolicy

    @property
    def errors_by_code(self) -> dict[str, GammaPublicErrorSpec]:
        return {item.code: item for item in self.errors}


@lru_cache(maxsize=1)
def load_gamma_provider_contract() -> GammaProviderContract:
    try:
        raw = json.loads(_PROVIDER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GammaProviderContractError(f"Cannot read {_PROVIDER_PATH}: {exc}") from exc
    if not isinstance(raw, dict):
        raise GammaProviderContractError("gamma_provider.json must be an object.")
    return _parse_provider_contract(raw)


def reset_gamma_provider_contract_cache() -> None:
    load_gamma_provider_contract.cache_clear()


def public_gamma_error_specs() -> dict[str, GammaPublicErrorSpec]:
    return load_gamma_provider_contract().errors_by_code


def accepted_logo_prefixes() -> tuple[str, ...]:
    """Storage refs the request may carry. Private prefixes are never egressed."""
    policy = load_gamma_provider_contract().reference_policy
    return policy.accepted_private_prefixes + configured_owned_https_prefixes()


def is_private_storage_reference(ref: str) -> bool:
    schemes = load_gamma_provider_contract().reference_policy.never_egress_schemes
    return ref.startswith(schemes)


def gamma_egress_reference(
    ref: str | None,
    *,
    owned_https_prefixes: tuple[str, ...] | None = None,
) -> str | None:
    """Return the reference only when Gamma may fetch it from an owned HTTPS host.

    Empty owned prefixes (no PUBLIC_API_BASE_URL, empty JSON list) are valid and
    block egress. Arbitrary `https://` is never enough on its own.
    """
    if ref is None or not ref.strip():
        return None
    policy = load_gamma_provider_contract().reference_policy
    if is_private_storage_reference(ref):
        return None
    prefixes = (
        owned_https_prefixes
        if owned_https_prefixes is not None
        else configured_owned_https_prefixes()
    )
    if not prefixes:
        return None
    if policy.egress_requires_https and not ref.startswith("https://"):
        return None
    if not ref.startswith(prefixes):
        return None
    return ref


def _parse_provider_contract(raw: dict[str, Any]) -> GammaProviderContract:
    errors = tuple(_parse_error_spec(item) for item in raw.get("errors") or ())
    if not errors:
        raise GammaProviderContractError("gamma_provider.json defines no public errors.")
    codes = [item.code for item in errors]
    if len(codes) != len(set(codes)):
        raise GammaProviderContractError("gamma_provider.json has duplicate error codes.")
    policy_raw = raw.get("reference_policy")
    if not isinstance(policy_raw, dict):
        raise GammaProviderContractError("gamma_provider.json is missing reference_policy.")
    return GammaProviderContract(
        schema_version=str(raw.get("schema_version") or ""),
        errors=errors,
        reference_policy=_parse_reference_policy(policy_raw),
    )


def _parse_error_spec(item: Any) -> GammaPublicErrorSpec:
    if not isinstance(item, dict):
        raise GammaProviderContractError("Each provider error must be an object.")
    try:
        classification = str(item["classification"])
        if classification not in _ALLOWED_ERROR_CLASSES:
            raise GammaProviderContractError(
                f"Unknown error classification '{classification}'."
            )
        return GammaPublicErrorSpec(
            code=str(item["code"]),
            classification=classification,  # type: ignore[arg-type]
            retryable=bool(item["retryable"]),
        )
    except KeyError as exc:
        raise GammaProviderContractError(f"Provider error is missing {exc}.") from exc


def _parse_reference_policy(raw: dict[str, Any]) -> GammaReferencePolicy:
    try:
        return GammaReferencePolicy(
            never_egress_schemes=tuple(str(item) for item in raw["never_egress_schemes"]),
            accepted_private_prefixes=tuple(
                str(item) for item in raw["accepted_private_prefixes"]
            ),
            owned_https_prefixes_from=str(raw["owned_https_prefixes_from"]),
            empty_owned_https_prefixes_valid=bool(raw["empty_owned_https_prefixes_valid"]),
            egress_requires_https=bool(raw["egress_requires_https"]),
            arbitrary_https_not_trusted=bool(raw["arbitrary_https_not_trusted"]),
            unfetchable_fallback=str(raw["unfetchable_fallback"]),
        )
    except KeyError as exc:
        raise GammaProviderContractError(f"reference_policy is missing {exc}.") from exc


def _error_spec(code: str) -> GammaPublicErrorSpec:
    specs = public_gamma_error_specs()
    spec = specs.get(code)
    if spec is None:
        raise GammaProviderContractError(
            f"Runtime error '{code}' is not in packages/contracts/gamma_provider.json."
        )
    return spec


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
    client_logo_placement: ClientLogoPlacement | None = None
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
        spec = public_gamma_error_specs().get(code)
        if spec is None:
            raise GammaProviderContractError(
                f"Runtime error '{code}' is not in packages/contracts/gamma_provider.json."
            )
        if spec.classification != classification or spec.retryable != retryable:
            raise GammaProviderContractError(
                f"Runtime error '{code}' does not match the frozen provider contract."
            )
        self.message = message
        self.code = spec.code
        self.classification = spec.classification
        self.retryable = spec.retryable


class GammaTimeoutError(GammaError):
    def __init__(self, message: str = "Gamma generation timed out.") -> None:
        spec = _error_spec("GAMMA_TIMEOUT")
        super().__init__(
            message,
            code=spec.code,
            classification=spec.classification,
            retryable=spec.retryable,
        )


class GammaAuthError(GammaError):
    def __init__(self, message: str = "Gamma credentials are missing or rejected.") -> None:
        spec = _error_spec("GAMMA_AUTH")
        super().__init__(
            message,
            code=spec.code,
            classification=spec.classification,
            retryable=spec.retryable,
        )


class GammaTemplateError(GammaError):
    def __init__(self, message: str) -> None:
        spec = _error_spec("GAMMA_TEMPLATE_LOCKED")
        super().__init__(
            message,
            code=spec.code,
            classification=spec.classification,
            retryable=spec.retryable,
        )


class GammaPayloadError(GammaError):
    def __init__(self, message: str) -> None:
        spec = _error_spec("GAMMA_PAYLOAD_INVALID")
        super().__init__(
            message,
            code=spec.code,
            classification=spec.classification,
            retryable=spec.retryable,
        )


class GammaRateLimitError(GammaError):
    def __init__(self, message: str = "Gamma rate limit is unknown without live access.") -> None:
        spec = _error_spec("GAMMA_RATE_LIMIT")
        super().__init__(
            message,
            code=spec.code,
            classification=spec.classification,
            retryable=spec.retryable,
        )


class GammaProviderError(GammaError):
    def __init__(self, message: str = "Gamma provider failed.") -> None:
        spec = _error_spec("GAMMA_PROVIDER_FAILED")
        super().__init__(
            message,
            code=spec.code,
            classification=spec.classification,
            retryable=spec.retryable,
        )


class GammaProvider(Protocol):
    """Outbound adapter. Fixture and live clients both implement this."""

    def generate(self, request: GammaGenerateRequest) -> GammaGenerateResult:
        ...
