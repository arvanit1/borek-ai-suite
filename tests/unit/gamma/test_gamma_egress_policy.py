from __future__ import annotations

import pytest

from app.services.gamma_generation import generate_with_egress_policy
from services.gamma.contract import (
    LOCKED_BOREK_TEMPLATE_ID,
    LOCKED_BOREK_TEMPLATE_VERSION,
    GammaContentSlot,
    GammaGenerateRequest,
    GammaPayloadError,
)
from services.gamma.fixture_client import FixtureGammaClient
from services.security.egress_filter import EgressPolicy


def _request() -> GammaGenerateRequest:
    return GammaGenerateRequest(
        template_id=LOCKED_BOREK_TEMPLATE_ID,
        template_version=LOCKED_BOREK_TEMPLATE_VERSION,
        opportunity_id="opp-1",
        presentation_version_id="version-1",
        output_formats=("pptx", "pdf"),
        slots=(
            GammaContentSlot(name="cover.title", value="Automation proposal"),
            GammaContentSlot(name="cover.client_name", value="Acme"),
        ),
    )


def _policy(*, confidential: frozenset[str] = frozenset()) -> EgressPolicy:
    return EgressPolicy(
        approved_providers=frozenset({"gamma"}),
        client_confidential_allowlist={"gamma": confidential},
    )


def test_gamma_boundary_allows_fully_classified_safe_slots() -> None:
    result = generate_with_egress_policy(
        _request(),
        provider=FixtureGammaClient(),
        policy=_policy(),
        slot_classifications={
            "cover.title": "internal",
            "cover.client_name": "public",
        },
    )

    assert result.branding_locked is True
    assert {artifact.format for artifact in result.artifacts} == {"pptx", "pdf"}


def test_gamma_boundary_fails_closed_for_unclassified_slot() -> None:
    with pytest.raises(GammaPayloadError, match="cover.client_name"):
        generate_with_egress_policy(
            _request(),
            provider=FixtureGammaClient(),
            policy=_policy(),
            slot_classifications={"cover.title": "internal"},
        )


def test_gamma_boundary_requires_exact_allowlist_for_confidential_slot() -> None:
    classifications = {
        "cover.title": "internal",
        "cover.client_name": "client_confidential",
    }
    with pytest.raises(GammaPayloadError, match="cover.client_name"):
        generate_with_egress_policy(
            _request(),
            provider=FixtureGammaClient(),
            policy=_policy(),
            slot_classifications=classifications,
        )

    result = generate_with_egress_policy(
        _request(),
        provider=FixtureGammaClient(),
        policy=_policy(confidential=frozenset({"/slots/cover.client_name"})),
        slot_classifications=classifications,
    )
    assert result.template_id == LOCKED_BOREK_TEMPLATE_ID
