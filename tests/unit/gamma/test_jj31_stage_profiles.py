"""JJ-31: stage profiles select cards, logo, pricing, and carry-forward copy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.gamma.contract import FORBIDDEN_BRANDING_KEYS, GammaPayloadError
from services.gamma.payload import build_gamma_content_payload
from services.gamma.slot_mapping import build_gamma_content_slots, resolve_journey_stage
from services.gamma.template import load_gamma_template

ROOT = Path(__file__).resolve().parents[3]
PRIOR_STAGE_FIXTURE = (
    ROOT / "packages" / "contracts" / "fixtures" / "gamma_payload" / "first_contact.json"
)


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


def _live_source(**overrides: object) -> dict:
    source = {
        "corpus_id": "borek-internal",
        "corpus_version": "2026.09.03",
        "document_id": "RC-2026-Q3",
        "document_type": "rate_card",
        "document_version": "2026.Q3.1",
        "fact_id": "price.invoice-3way.senior-consultant.day-rate",
        "provenance_marker": "es39",
    }
    source.update(overrides)
    return source


def _stage_facts() -> dict:
    return {
        "answered": [
            {
                "kind": "service",
                "status": "answered",
                "statement": "Invoice 3-way Match matches invoices to POs.",
                "payload": {"service_key": "invoice_3way_match"},
                "sources": [
                    _live_source(
                        document_id="SVC-INV3WAY-v1",
                        document_type="service_definition",
                        fact_id="service.invoice-3way.definition",
                    )
                ],
            },
            {
                "kind": "reference",
                "status": "answered",
                "statement": "A comparable three-way match went live at a DAX manufacturer.",
                "payload": {"client": "DAX manufacturer"},
                "sources": [
                    _live_source(
                        document_id="REF-INV3WAY-v1",
                        document_type="reference",
                        fact_id="ref.invoice-3way.dax",
                    )
                ],
            },
            {
                "kind": "staffing",
                "status": "answered",
                "payload": {"headcount": 4, "total_fte": "2.6"},
                "sources": [
                    _live_source(
                        document_id="STAFF-INV3WAY-v1",
                        document_type="staffing_profile",
                        fact_id="staff.invoice-3way.core-team",
                    )
                ],
            },
            {
                "kind": "pricing",
                "status": "answered",
                "statement": "Senior Consultant day rate is EUR 1250.00 (indicative).",
                "payload": {
                    "amount": "1250.00",
                    "currency": "EUR",
                    "unit": "day",
                    "indicative": True,
                },
                "sources": [_live_source()],
            },
        ]
    }


def test_missing_stage_is_payload_invalid() -> None:
    with pytest.raises(GammaPayloadError, match="Journey stage is required") as missing:
        resolve_journey_stage(None)
    assert missing.value.code == "GAMMA_PAYLOAD_INVALID"

    with pytest.raises(GammaPayloadError, match="Journey stage is required") as payload_missing:
        build_gamma_content_payload(
            opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
            framework=_confirmed({"1": "Summary."}),
            stage=None,
        )
    assert payload_missing.value.code == "GAMMA_PAYLOAD_INVALID"


def test_unknown_stage_is_payload_invalid() -> None:
    with pytest.raises(GammaPayloadError, match="Unknown journey stage") as unknown:
        build_gamma_content_slots(
            opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
            framework=_confirmed({"1": "Summary."}),
            stage="pitch_v4",
        )
    assert unknown.value.code == "GAMMA_PAYLOAD_INVALID"


def test_first_contact_omits_pricing_logo_and_excluded_cards() -> None:
    payload = build_gamma_content_payload(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_confirmed(
            {
                "1": "Borek information pack.",
                "2": "Acme's process today.",
                "9": "EUR 1250.00 / day (indicative).",
                "13": "Book a deepening conversation.",
            },
            company_facts=_stage_facts(),
        ),
        stage="first_contact",
        client_logo_ref="artifact:logos/acme.png",
    )
    names = {slot["name"] for slot in payload["slots"]}
    blob = " ".join(slot["value"] for slot in payload["slots"])
    kinds = {item["kind"] for item in payload["grounded_facts"]}
    profile_slots = {slot.name for slot in load_gamma_template().slots_for_stage("first_contact")}

    assert payload["client_logo_ref"] is None
    assert names <= profile_slots
    assert "team.body" not in names
    assert "success_metrics.body" not in names
    assert "pricing" not in kinds
    assert "staffing" not in kinds
    assert "reference" not in kinds
    assert "1250" not in blob
    assert "Acme's process today." not in blob
    assert "Borek information pack." in blob
    assert not FORBIDDEN_BRANDING_KEYS & names
    assert all(
        "9" not in (load_gamma_template().slot(name).source_chapter_ids)
        for name in names
        if name in set(load_gamma_template().slot_names)
    )


def test_deepening_carries_references_and_the_logo() -> None:
    payload = build_gamma_content_payload(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_confirmed(
            {
                "1": "Tailored pitch for Acme.",
                "2": "Acme's process today.",
                "4": "The matching gap.",
                "9": "EUR 1250.00 / day (indicative).",
                "13": "Confirm the pilot scope.",
            },
            company_facts=_stage_facts(),
        ),
        stage="deepening",
        client_logo_ref="artifact:logos/acme.png",
    )
    names = {slot["name"] for slot in payload["slots"]}
    blob = " ".join(slot["value"] for slot in payload["slots"])
    kinds = {item["kind"] for item in payload["grounded_facts"]}

    assert payload["client_logo_ref"] == "artifact:logos/acme.png"
    assert "problem_solution.body" in names
    assert "team.body" in names
    assert "reference" in kinds
    assert "staffing" in kinds
    assert "pricing" not in kinds
    assert "DAX manufacturer" in blob or "comparable three-way match" in blob
    assert "4 people / 2.6 FTE" in blob
    assert "1250" not in blob


def test_concretisation_prices_are_indicative_and_grounded() -> None:
    payload = build_gamma_content_payload(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_confirmed(
            {
                "1": "Priced proposal for Acme.",
                "9": "EUR 1250.00 / day (indicative).",
                "13": "Confirm the indicative rate card.",
            },
            company_facts=_stage_facts(),
        ),
        stage="concretisation",
        client_logo_ref="artifact:logos/acme.png",
    )
    blob = " ".join(slot["value"] for slot in payload["slots"])
    prices = [item for item in payload["grounded_facts"] if item["kind"] == "pricing"]
    assert prices
    for price in prices:
        assert price["payload"]["indicative"] is True
        provenance = price["provenance"]
        assert provenance["marker"] == "es39"
        assert provenance["document_id"] == "RC-2026-Q3"
        assert provenance["fact_id"]
    assert "1250" not in blob
    assert payload["client_logo_ref"] == "artifact:logos/acme.png"


def test_concretisation_refuses_an_ungrounded_price() -> None:
    with pytest.raises(GammaPayloadError, match="Ungrounded price refused") as refused:
        build_gamma_content_payload(
            opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
            framework=_confirmed(
                {"1": "Summary.", "9": "EUR 9999.00 / day (indicative)."},
                company_facts=_stage_facts(),
            ),
            stage="concretisation",
        )
    assert refused.value.code == "GAMMA_PAYLOAD_INVALID"


def test_deepening_reuses_identifiable_first_contact_copy() -> None:
    prior = json.loads(PRIOR_STAGE_FIXTURE.read_text(encoding="utf-8"))
    payload = build_gamma_content_payload(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_confirmed({"13": "Confirm the pilot scope."}),
        stage="deepening",
        client_logo_ref="artifact:logos/acme.png",
        prior_stage_context=prior,
    )
    blob = " ".join(slot["value"] for slot in payload["slots"])
    names = {slot["name"] for slot in payload["slots"]}
    kinds = {item["kind"] for item in payload["grounded_facts"]}

    assert "Borek information pack." in blob
    assert names >= {"cover.title", "cover.subtitle", "executive_summary.body", "next_steps.body"}
    assert "service" in kinds
    assert "pricing" not in kinds
    assert payload["client_logo_ref"] == "artifact:logos/acme.png"
