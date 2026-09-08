"""ES-40 — Gamma content payload from a confirmed Framework plus retrieved facts."""

from __future__ import annotations

import pytest

from services.gamma.contract import FORBIDDEN_BRANDING_KEYS, GammaPayloadError
from services.gamma.slot_mapping import build_gamma_content_slots
from services.gamma.template import load_gamma_template


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


def test_unconfirmed_framework_is_rejected() -> None:
    with pytest.raises(GammaPayloadError, match="confirmed"):
        build_gamma_content_slots(
            opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
            framework={"status": "draft", "chapters": [{"chapter_id": "1", "body": "Summary."}]},
        )
    with pytest.raises(GammaPayloadError, match="confirmed"):
        build_gamma_content_slots(
            opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
            framework={"chapters": [{"chapter_id": "1", "body": "Summary."}]},
        )


def test_payload_is_named_content_slots_only() -> None:
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_confirmed({"1": "Management summary.", "13": "Confirm the pilot."}),
    )
    names = [slot.name for slot in slots]
    assert "cover.title" in names
    assert "cover.client_name" in names
    assert not FORBIDDEN_BRANDING_KEYS & set(names)
    assert "brand_color" not in names
    assert "theme" not in names


def test_chapter_nine_pricing_never_reaches_gamma_slots() -> None:
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_confirmed(
            {
                "1": "Summary.",
                "9": "EUR 1250.00 / day (indicative). corpus 2026.09.03, RC-DUMMY-2026-Q3.",
                "10": "Likely 3 weeks.",
            },
            company_facts={
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
                                "corpus_version": "2026.09.03",
                                "document_id": "RC-DUMMY-2026-Q3",
                                "fact_id": "price.invoice-3way.senior-consultant.day-rate",
                            }
                        ],
                    }
                ]
            },
        ),
    )
    blob = " ".join(slot.value for slot in slots)
    assert "1250" not in blob
    assert "RC-DUMMY-2026-Q3" not in blob


def test_retrieved_staffing_and_service_facts_fill_allowed_slots() -> None:
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_confirmed(
            {"1": "Summary."},
            company_facts={
                "answered": [
                    {
                        "kind": "staffing",
                        "status": "answered",
                        "payload": {"headcount": 4, "total_fte": "2.6"},
                        "sources": [
                            {
                                "corpus_version": "2026.09.03",
                                "document_id": "STAFF-DUMMY-INV3WAY-v1",
                                "fact_id": "staff.invoice-3way.core-team",
                            }
                        ],
                    },
                    {
                        "kind": "service",
                        "status": "answered",
                        "statement": "Invoice 3-way Match matches invoices to POs.",
                        "payload": {"service_key": "invoice_3way_match"},
                        "sources": [
                            {
                                "corpus_version": "2026.09.03",
                                "document_id": "SVC-DUMMY-INV3WAY-v1",
                                "fact_id": "service.invoice-3way.definition",
                            }
                        ],
                    },
                ]
            },
        ),
    )
    by_name = {slot.name: slot.value for slot in slots}
    assert "4 people / 2.6 FTE" in by_name["team.body"]
    assert "staff.invoice-3way.core-team" in by_name["team.body"]
    assert "corpus 2026.09.03" in by_name["team.body"]
    assert "Invoice 3-way Match matches invoices to POs" in by_name["problem_solution.body"]
    assert "service.invoice-3way.definition" in by_name["problem_solution.body"]


def test_unknown_company_facts_do_not_invent_numbers() -> None:
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Warehouse", "client_name": "Acme"},
        framework=_confirmed(
            {"1": "Summary."},
            company_facts={
                "answered": [],
                "unknown": [{"kind": "pricing", "status": "unknown", "reason": "no_supported_fact"}],
            },
        ),
    )
    blob = " ".join(slot.value for slot in slots)
    assert "1250" not in blob
    assert "4 people" not in blob
    assert "team.body" not in {slot.name for slot in slots}


def test_process_flow_emits_labels_not_node_ids() -> None:
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_confirmed(
            {
                "2": [
                    {
                        "block": "process_flow",
                        "nodes": [
                            {"id": "n1", "label": "Intake mailbox", "kind": "start_end"},
                            {"id": "n2", "label": "Match invoice", "kind": "agent"},
                        ],
                        "edges": [{"from": "n1", "to": "n2"}],
                    }
                ]
            }
        ),
    )
    flow = next(slot for slot in slots if slot.name == "process_flow.body")
    assert "Intake mailbox" in flow.value
    assert "Match invoice" in flow.value
    assert "n1" not in flow.value
    assert "start_end" not in flow.value


def test_store_row_unwraps_confirmed_framework_json() -> None:
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework={
            "status": "confirmed",
            "framework_json": _confirmed({"13": "Pilot next Tuesday."}),
        },
    )
    assert any(slot.name == "next_steps.body" and "Pilot next Tuesday" in slot.value for slot in slots)


def test_every_contract_slot_can_be_filled_from_confirmed_chapters() -> None:
    bodies = {str(index): f"Chapter {index} body." for index in range(14)}
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_confirmed(bodies),
    )
    assert {slot.name for slot in slots} == set(load_gamma_template().slot_names)
