"""AT-60A: frozen provider error contract and owned-host rule cannot drift."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.gamma.contract import (
    GammaAuthError,
    GammaError,
    GammaPayloadError,
    GammaProviderContractError,
    GammaProviderError,
    GammaPublicErrorSpec,
    GammaRateLimitError,
    GammaTemplateError,
    GammaTimeoutError,
    accepted_logo_prefixes,
    gamma_egress_reference,
    is_private_storage_reference,
    load_gamma_provider_contract,
    public_gamma_error_specs,
)
from services.gamma.template import load_gamma_template

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "packages" / "contracts" / "gamma_provider.json"

_RUNTIME_ERROR_TYPES: tuple[type[GammaError], ...] = (
    GammaTimeoutError,
    GammaAuthError,
    GammaTemplateError,
    GammaPayloadError,
    GammaRateLimitError,
    GammaProviderError,
)


def _sample(error_type: type[GammaError]) -> GammaError:
    try:
        return error_type()  # type: ignore[call-arg]
    except TypeError:
        return error_type("contract probe")


def _runtime_specs() -> dict[str, GammaPublicErrorSpec]:
    discovered = GammaError.__subclasses__()
    assert set(discovered) == set(_RUNTIME_ERROR_TYPES)
    specs: dict[str, GammaPublicErrorSpec] = {}
    for error_type in discovered:
        sample = _sample(error_type)
        specs[sample.code] = GammaPublicErrorSpec(
            code=sample.code,
            classification=sample.classification,
            retryable=sample.retryable,
        )
    return specs


def test_provider_contract_file_is_the_source_of_truth() -> None:
    raw = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract = load_gamma_provider_contract()
    assert raw["schema_version"] == "1.0"
    assert contract.schema_version == "1.0"
    assert {item["code"] for item in raw["errors"]} == set(public_gamma_error_specs())


def test_runtime_public_codes_match_the_frozen_contract_exactly() -> None:
    runtime = _runtime_specs()
    frozen = public_gamma_error_specs()
    assert set(runtime) == set(frozen)
    for code, spec in frozen.items():
        assert runtime[code] == spec


def test_unknown_runtime_or_contract_code_fails_closed() -> None:
    with pytest.raises(GammaProviderContractError, match="not in packages/contracts"):
        GammaError(
            "probe",
            code="GAMMA_UNKNOWN_CODE",
            classification="provider",
            retryable=False,
        )
    with pytest.raises(GammaProviderContractError, match="does not match the frozen"):
        GammaError(
            "probe",
            code="GAMMA_TIMEOUT",
            classification="timeout",
            retryable=False,
        )


def test_retryability_matches_runtime_and_at57() -> None:
    from app.services.job_retry import is_transient_failure

    for error_type in _RUNTIME_ERROR_TYPES:
        sample = _sample(error_type)
        spec = public_gamma_error_specs()[sample.code]
        assert sample.retryable is spec.retryable
        assert is_transient_failure(sample) is spec.retryable


def test_empty_owned_https_prefixes_are_valid_and_block_egress() -> None:
    policy = load_gamma_provider_contract().reference_policy
    assert policy.empty_owned_https_prefixes_valid is True
    assert load_gamma_template().client_logo.signed_url_prefixes == ()
    assert set(policy.accepted_private_prefixes) <= set(accepted_logo_prefixes())
    assert gamma_egress_reference("https://evil.example/logo.png") is None
    assert gamma_egress_reference("https://logos.borek.example/acme.png") is None


def test_private_artifact_and_s3_references_never_egress() -> None:
    assert is_private_storage_reference("artifact:logos/acme.png") is True
    assert is_private_storage_reference("s3://borek-client-logos/acme.png") is True
    assert gamma_egress_reference("artifact:logos/acme.png") is None
    assert gamma_egress_reference("s3://borek-client-logos/acme.png") is None
    assert (
        gamma_egress_reference(
            "artifact:logos/acme.png",
            owned_https_prefixes=("https://logos.borek.example/",),
        )
        is None
    )


def test_arbitrary_https_is_not_trusted_even_when_a_host_is_configured() -> None:
    policy = load_gamma_provider_contract().reference_policy
    assert policy.arbitrary_https_not_trusted is True
    assert policy.egress_requires_https is True
    owned = ("https://logos.borek.example/",)
    assert (
        gamma_egress_reference(
            "https://logos.borek.example/acme.png?sig=abc",
            owned_https_prefixes=owned,
        )
        == "https://logos.borek.example/acme.png?sig=abc"
    )
    assert gamma_egress_reference("https://evil.example/logo.png", owned_https_prefixes=owned) is None
    assert (
        gamma_egress_reference("http://logos.borek.example/acme.png", owned_https_prefixes=owned)
        is None
    )


def test_unfetchable_fallback_name_is_frozen_for_jj29() -> None:
    policy = load_gamma_provider_contract().reference_policy
    assert policy.unfetchable_fallback == "provider_could_not_fetch_reference"
    assert policy.owned_https_prefixes_from == "gamma_template.client_logo.signed_url_prefixes"
