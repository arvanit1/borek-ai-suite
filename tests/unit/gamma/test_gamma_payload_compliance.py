"""Gamma payload compliance — commercial content at the provider boundary."""

from __future__ import annotations

import pytest

from services.gamma.contract import GammaPayloadError
from services.gamma.payload import build_gamma_content_payload
from services.gamma.payload_compliance import (
    apply_gamma_payload_compliance,
    contains_prohibited_gamma_commercial_text,
    find_prohibited_gamma_commercial_paths,
    repair_gamma_slot_text,
    validate_gamma_payload_compliance,
)
from services.gamma.slot_mapping import build_gamma_content_slots


def _confirmed(bodies: dict[str, object], *, company_facts: dict | None = None) -> dict:
    payload: dict = {
        "status": "confirmed",
        "chapters": [
            {"chapter_id": chapter_id, "title": f"Chapter {chapter_id}", "body": body}
            for chapter_id, body in bodies.items()
        ],
    }
    if company_facts is not None:
        payload["generation_meta"] = {"company_facts": company_facts}
    return payload


def _live_pricing_facts() -> dict:
    return {
        "answered": [
            {
                "kind": "pricing",
                "status": "answered",
                "statement": "Senior Consultant day rate is EUR 1250.00.",
                "payload": {
                    "amount": "1250.00",
                    "currency": "EUR",
                    "unit": "day",
                    "indicative": True,
                },
                "sources": [
                    {
                        "corpus_id": "borek-internal",
                        "corpus_version": "2026.09.03",
                        "document_id": "RC-2026-Q3",
                        "document_type": "rate_card",
                        "document_version": "2026.Q3.1",
                        "fact_id": "price.invoice-3way.senior-consultant.day-rate",
                        "provenance_marker": "es39",
                    }
                ],
            }
        ]
    }


def test_live_manual_smoke_chapter_one_business_case_is_repaired() -> None:
    """Reproduce BT-30 manual smoke: chapter 1 ROI row leaked into first_contact slots."""
    offending = (
        "Accounts Payable processes around 3,000 supplier invoices per month.\n\n"
        "Investment: ~EUR 22500 build (4.5 weeks) · ~EUR 400/month run cost"
    )
    framework = _confirmed(
        {
            "1": offending,
            "4": "Automate invoice matching against purchase orders.",
            "13": "Confirm the pilot scope next week.",
        }
    )
    opportunity = {
        "opportunity_name": "English Phase-1 Acceptance",
        "client_name": "BT-27 Live Invoice Co",
    }

    assert contains_prohibited_gamma_commercial_text(offending)
    with pytest.raises(GammaPayloadError, match="prohibited commercial content"):
        validate_gamma_payload_compliance(
            {"slots": [{"name": "executive_summary.body", "value": offending}]},
            pricing_permitted=False,
            grounding=None,
        )

    payload = build_gamma_content_payload(
        opportunity=opportunity,
        framework=framework,
        stage="first_contact",
    )
    blob = " ".join(slot["value"] for slot in payload["slots"])
    assert "3,000 supplier invoices" in blob
    assert "400" not in blob
    assert "22500" not in blob
    assert find_prohibited_gamma_commercial_paths(payload) == []


def test_repair_preserves_non_commercial_paragraphs() -> None:
    repaired = repair_gamma_slot_text(
        "Process summary stays.\n\nInvestment: ~EUR 400/month run cost\n\nNext actions remain."
    )
    assert "Process summary stays." in repaired
    assert "Next actions remain." in repaired
    assert "400" not in repaired
    assert not contains_prohibited_gamma_commercial_text(repaired)


def test_non_commercial_deck_unchanged() -> None:
    slots = (
        __import__("services.gamma.contract", fromlist=["GammaContentSlot"]).GammaContentSlot(
            "context.summary",
            "Manual invoice checks take twelve working days.",
        ),
    )
    repaired = apply_gamma_payload_compliance(slots, pricing_permitted=False)
    assert repaired[0].value == slots[0].value


def test_concretisation_still_refuses_ungrounded_price() -> None:
    with pytest.raises(GammaPayloadError, match="Ungrounded price refused"):
        build_gamma_content_payload(
            opportunity={"opportunity_name": "Invoice match", "client_name": "Acme"},
            framework=_confirmed(
                {"1": "Summary.", "9": "EUR 9999.00 / day (indicative)."},
                company_facts=_live_pricing_facts(),
            ),
            stage="concretisation",
        )


def test_optional_commercial_subtitle_is_omitted_from_payload() -> None:
    framework = _confirmed(
        {
            "1": "Operational summary without pricing.",
            "4": "Automate invoice matching.",
            "13": "Confirm pilot scope.",
        },
        company_facts=None,
    )
    framework["cover"] = {
        "tagline": "Invoice automation — EUR 22,500 build, 9.6-month payback",
    }
    payload = build_gamma_content_payload(
        opportunity={"opportunity_name": "Invoice match", "client_name": "Acme"},
        framework=framework,
        stage="first_contact",
    )
    names = {slot["name"] for slot in payload["slots"]}
    assert "cover.subtitle" not in names


def test_validate_gamma_payload_compliance_fails_when_repair_insufficient() -> None:
    payload = {
        "slots": [
            {"name": "executive_summary.body", "value": "Still contains EUR 400/month run cost"}
        ]
    }
    with pytest.raises(GammaPayloadError, match="prohibited commercial content"):
        validate_gamma_payload_compliance(
            payload,
            pricing_permitted=False,
            grounding=None,
        )
