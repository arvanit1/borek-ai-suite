"""Stage 2 FE-06: exact claim-to-Knowledge entry provenance."""

from __future__ import annotations

import copy

import pytest

from services.framework.source_traceability import AtomicTraceabilityError, attach_block_source_refs
from services.knowledge_model.entry_ids import ensure_knowledge_entry_ids


def _entry(statement: str, turn: int) -> dict:
    model = {
        "transcript_id": "transcript-1",
        "facts": [
            {
                "statement": statement,
                "origin": "SOURCE_FACT",
                "confidence": "high",
                "source_refs": [
                    {
                        "conversation_id": "C1",
                        "speaker_role": "operator",
                        "excerpt_pointer": f"turn:{turn}",
                    }
                ],
            }
        ],
    }
    ensure_knowledge_entry_ids(model)
    entry = model["facts"][0]
    entry["bucket"] = "facts"
    return entry


def _framework(block: dict) -> dict:
    return {
        "generation_meta": {},
        "chapters": [{"chapter_id": "2", "body": [block], "source_refs": []}],
    }


def test_atomic_claim_derives_refs_from_exact_entry_id() -> None:
    entry = _entry("AP must approve invoices.", 3)
    block = {
        "block": "table",
        "rows": [["Approval", "AP must approve invoices."]],
        "source_claims": [
            {
                "path": "/rows/0/1",
                "claim": "AP must approve invoices.",
                "knowledge_entry_ids": [entry["entry_id"]],
                "source_refs": [{"conversation_id": "C99", "speaker_role": "fake", "excerpt_pointer": "turn:99"}],
            }
        ],
    }
    framework = _framework(block)

    attach_block_source_refs(framework, [entry])

    claim = block["source_claims"][0]
    assert claim["source_refs"] == entry["source_refs"]
    assert block["source_refs"] == entry["source_refs"]
    assert framework["generation_meta"]["traceability_version"] == "atomic-v1"


def test_atomic_claim_rejects_valid_pointer_to_wrong_entry() -> None:
    approval = _entry("AP must approve invoices.", 3)
    supplier = _entry("Supplier records are available.", 8)
    framework = _framework(
        {
            "block": "prose",
            "text": "AP must approve invoices.",
            "source_claims": [
                {
                    "path": "/text",
                    "claim": "AP must approve invoices.",
                    "knowledge_entry_ids": [supplier["entry_id"]],
                    "source_refs": [],
                }
            ],
        }
    )

    with pytest.raises(AtomicTraceabilityError, match="does not exactly match"):
        attach_block_source_refs(framework, [approval, supplier])


def test_atomic_claim_rejects_stale_value_and_unknown_entry() -> None:
    entry = _entry("Grounded value", 1)
    original = {
        "block": "prose",
        "text": "Edited value",
        "source_claims": [
            {
                "path": "/text",
                "claim": "Old value",
                "knowledge_entry_ids": [entry["entry_id"]],
                "source_refs": [],
            }
        ],
    }

    with pytest.raises(AtomicTraceabilityError, match="does not match"):
        attach_block_source_refs(_framework(copy.deepcopy(original)), [entry])

    original["source_claims"][0]["claim"] = "Edited value"
    original["source_claims"][0]["knowledge_entry_ids"] = ["KE-000000000000000000000000"]
    with pytest.raises(AtomicTraceabilityError, match="unknown Knowledge entry"):
        attach_block_source_refs(_framework(original), [entry])


def test_legacy_block_does_not_receive_fuzzy_reference() -> None:
    entry = _entry("Supplier approval is manual.", 2)
    block = {"block": "prose", "text": "Supplier approval is automatic."}
    framework = _framework(block)

    attach_block_source_refs(framework, [entry])

    assert "source_refs" not in block
    assert "traceability_version" not in framework["generation_meta"]
