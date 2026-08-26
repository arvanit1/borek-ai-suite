"""ES-8 — conflicting values become a structured conflict object."""

from __future__ import annotations

from services.knowledge_model.contradictions import detect_contradictions


def _entry(statement: str, conversation_id: str, turn: int) -> dict:
    return {
        "statement": statement,
        "origin": "SOURCE_FACT",
        "confidence": "high",
        "source_refs": [
            {
                "conversation_id": conversation_id,
                "speaker_role": "Sandra",
                "excerpt_pointer": f"turn:{turn}",
            }
        ],
    }


def test_two_conflicting_values_become_conflict_object() -> None:
    model = {
        "facts": [
            _entry("Tolerance is EUR 1.00.", "C5", 0),
            _entry("Tolerance is EUR 0.50.", "C8", 1),
        ],
        "stated_requirements": [],
        "constraints": [],
        "named_systems": [],
        "named_rules": [],
        "named_exceptions": [],
        "people_and_roles": [],
        "timeline_mentions": [],
        "risks": [],
        "unknowns": [],
    }
    conflicts = detect_contradictions(model)
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict["requires_clarification"] is True
    assert "EUR 1.00" in conflict["values"][0] or "EUR 1.00" in conflict["values"][1]
    assert "EUR 0.50" in conflict["values"][0] or "EUR 0.50" in conflict["values"][1]
    assert "C5:turn:0" in conflict["source_ids"]
    assert "C8:turn:1" in conflict["source_ids"]
    assert model["facts"][0]["statement"] == "Tolerance is EUR 1.00."
    assert model["facts"][1]["statement"] == "Tolerance is EUR 0.50."


def test_matching_statements_are_not_conflicts() -> None:
    model = {
        "facts": [
            _entry("The process uses the ERP.", "C1", 0),
            _entry("The process uses the ERP.", "C1", 1),
        ],
        "stated_requirements": [],
        "constraints": [],
        "named_systems": [],
        "named_rules": [],
        "named_exceptions": [],
        "people_and_roles": [],
        "timeline_mentions": [],
        "risks": [],
        "unknowns": [],
    }
    assert detect_contradictions(model) == []
