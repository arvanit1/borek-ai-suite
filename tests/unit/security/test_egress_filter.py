from __future__ import annotations

from services.security.egress_filter import (
    Classification,
    EgressPolicy,
    filter_external_payload,
)


def _policy() -> EgressPolicy:
    return EgressPolicy(
        approved_providers=frozenset({"openai", "anthropic", "gamma"}),
        client_confidential_allowlist={
            "gamma": frozenset({"/client/name", "/client/priorities/0"}),
        },
    )


def test_blocks_unclassified_and_restricted_fields() -> None:
    decision = filter_external_payload(
        {
            "title": "Automation proposal",
            "strategy": "Restricted acquisition plan",
            "unclassified": "must not leak",
        },
        provider="gamma",
        classifications={
            "/title": Classification.INTERNAL,
            "/strategy": Classification.RESTRICTED,
        },
        policy=_policy(),
    )

    assert decision.payload == {"title": "Automation proposal"}
    assert decision.allowed_paths == ("/title",)
    assert decision.blocked_paths == ("/strategy", "/unclassified")


def test_client_confidential_fields_require_exact_provider_allowlist() -> None:
    payload = {
        "client": {
            "name": "Acme",
            "architecture": "Private network design",
            "priorities": ["Faster close", "Confidential expansion"],
        }
    }
    classifications = {
        "/client/name": "client_confidential",
        "/client/architecture": "client_confidential",
        "/client/priorities/0": "client_confidential",
        "/client/priorities/1": "client_confidential",
    }

    decision = filter_external_payload(
        payload,
        provider="gamma",
        classifications=classifications,
        policy=_policy(),
    )

    assert decision.payload == {
        "client": {"name": "Acme", "priorities": ["Faster close"]}
    }
    assert set(decision.blocked_paths) == {
        "/client/architecture",
        "/client/priorities/1",
    }


def test_unapproved_provider_receives_empty_payload() -> None:
    decision = filter_external_payload(
        {"summary": "Internal opportunity"},
        provider="unknown-provider",
        classifications={"/summary": "internal"},
        policy=_policy(),
    )

    assert decision.payload == {}
    assert decision.allowed_paths == ()
    assert decision.blocked_paths == ("/summary",)


def test_parent_path_classification_applies_to_descendants() -> None:
    decision = filter_external_payload(
        {"frameworkObject": {"chapters": [{"body": "Client process"}]}},
        provider="openai",
        classifications={"/frameworkObject": "client_confidential"},
        policy=EgressPolicy(
            approved_providers=frozenset({"openai"}),
            client_confidential_allowlist={"openai": frozenset({"/frameworkObject"})},
        ),
    )

    assert decision.payload == {"frameworkObject": {"chapters": [{"body": "Client process"}]}}
    assert "/frameworkObject/chapters/0/body" in decision.allowed_paths


def test_originally_empty_allowed_containers_are_kept() -> None:
    decision = filter_external_payload(
        {"chapterLayoutGuidance": {"chapters": []}},
        provider="openai",
        classifications={"/chapterLayoutGuidance": "internal"},
        policy=EgressPolicy(approved_providers=frozenset({"openai"})),
    )

    assert decision.payload == {"chapterLayoutGuidance": {"chapters": []}}
    assert "/chapterLayoutGuidance/chapters" in decision.allowed_paths


def test_empty_containers_do_not_reveal_blocked_structure() -> None:
    decision = filter_external_payload(
        {"client": {"restricted_notes": "secret"}},
        provider="gamma",
        classifications={"/client/restricted_notes": "restricted"},
        policy=_policy(),
    )

    assert decision.payload == {}
