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


def test_atomic_claim_rewrites_stale_claim_text_to_the_cell() -> None:
    entry = _entry("Edited value is grounded.", 1)
    framework = _framework(
        {
            "block": "prose",
            "text": "Edited value is grounded.",
            "source_claims": [
                {
                    "path": "/text",
                    "claim": "Old paraphrased wording",
                    "knowledge_entry_ids": [entry["entry_id"]],
                    "source_refs": [],
                }
            ],
        }
    )
    attach_block_source_refs(framework, [entry])
    assert framework["chapters"][0]["body"][0]["source_claims"][0]["claim"] == "Edited value is grounded."


def test_atomic_claim_rejects_stale_value() -> None:
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

    with pytest.raises(AtomicTraceabilityError, match="does not exactly match"):
        attach_block_source_refs(_framework(copy.deepcopy(original)), [entry])


def test_atomic_claim_skips_unknown_entry_and_stamps_supporting_live_cell() -> None:
    entry = _entry("AP must approve invoices.", 3)
    framework = {
        "generation_meta": {"llm_used": True},
        "chapters": [
            {
                "chapter_id": "2",
                "body": [
                    {
                        "block": "prose",
                        "text": "AP must approve invoices.",
                        "source_claims": [
                            {
                                "path": "/text",
                                "claim": "AP must approve invoices.",
                                "knowledge_entry_ids": ["KE-000000000000000000000000"],
                            }
                        ],
                    }
                ],
                "source_refs": [],
            }
        ],
    }
    attach_block_source_refs(framework, [entry])
    claims = framework["chapters"][0]["body"][0]["source_claims"]
    assert claims[0]["knowledge_entry_ids"] == [entry["entry_id"]]
    assert claims[0]["path"] == "/text"


def test_atomic_claim_accepts_bare_text_path() -> None:
    entry = _entry("AP must approve invoices.", 3)
    framework = _framework(
        {
            "block": "prose",
            "text": "AP must approve invoices.",
            "source_claims": [
                {
                    "path": "text",
                    "claim": "paraphrase",
                    "knowledge_entry_ids": [entry["entry_id"]],
                    "source_refs": [],
                }
            ],
        }
    )
    attach_block_source_refs(framework, [entry])
    assert framework["chapters"][0]["body"][0]["source_claims"][0]["path"] == "/text"


def test_atomic_claim_skips_unusable_paths_without_failing_the_block() -> None:
    entry = _entry("AP must approve invoices.", 3)
    framework = _framework(
        {
            "block": "prose",
            "text": "AP must approve invoices.",
            "source_claims": [
                {"path": "", "claim": "x", "knowledge_entry_ids": [entry["entry_id"]]},
                {
                    "path": "/text",
                    "claim": "AP must approve invoices.",
                    "knowledge_entry_ids": [entry["entry_id"]],
                    "source_refs": [],
                },
            ],
        }
    )
    attach_block_source_refs(framework, [entry])
    assert len(framework["chapters"][0]["body"][0]["source_claims"]) == 1


def test_live_missing_claims_are_stamped_from_supporting_entries() -> None:
    entry = _entry("Clerks spend 110 staff-hours on matching each month.", 1)
    entry["metric"] = {"kind": "automatable_hours_mo", "value": 110}
    framework = {
        "generation_meta": {"llm_used": True},
        "chapters": [
            {
                "chapter_id": "2",
                "body": [{"block": "prose", "text": "Clerks spend 110 staff-hours on matching each month."}],
                "source_refs": [],
            }
        ],
    }
    attach_block_source_refs(framework, [entry])
    claims = framework["chapters"][0]["body"][0]["source_claims"]
    assert claims[0]["path"] == "/text"
    assert claims[0]["knowledge_entry_ids"] == [entry["entry_id"]]
    assert claims[0]["source_refs"] == entry["source_refs"]


def test_legacy_block_does_not_receive_fuzzy_reference() -> None:
    entry = _entry("Supplier approval is manual.", 2)
    block = {"block": "prose", "text": "Supplier approval is automatic."}
    framework = _framework(block)

    attach_block_source_refs(framework, [entry])

    assert "source_refs" not in block
    assert "traceability_version" not in framework["generation_meta"]
