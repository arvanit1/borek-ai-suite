"""ES-10 conflict merge: later or confirmed source wins; never silent drop."""

from services.framework.assembly import assemble_from_knowledge
from services.framework.conflict_resolution import merge_knowledge_models


def _model(
    conversation_id: str,
    statement: str,
    turn: int,
    *,
    status: str | None = None,
    confirmed: bool = False,
) -> dict:
    entry = {
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
    if confirmed:
        entry["confirmed"] = True
    payload = {
        "conversation_id": conversation_id,
        "facts": [entry],
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
    if status:
        payload["status"] = status
    return payload


def test_later_conversation_wins_and_conflict_is_logged() -> None:
    early = _model("C5", "Tolerance is EUR 1.00.", 0)
    later = _model("C8", "Tolerance is EUR 0.50.", 1)
    buckets, open_items = merge_knowledge_models([early, later])
    assert [item["statement"] for item in buckets["facts"]] == ["Tolerance is EUR 0.50."]
    assert open_items
    assert "EUR 1.00" in open_items[0]["description"]
    assert "EUR 0.50" in open_items[0]["description"]
    assert "Later source kept" in open_items[0]["description"]
    assert "C5:turn:0" in open_items[0]["description"]
    assert "C8:turn:1" in open_items[0]["description"]


def test_confirmed_source_wins_over_later_unconfirmed() -> None:
    confirmed = _model("C5", "Tolerance is EUR 1.00.", 0, status="confirmed")
    later_draft = _model("C8", "Tolerance is EUR 0.50.", 1)
    buckets, open_items = merge_knowledge_models([later_draft, confirmed])
    assert [item["statement"] for item in buckets["facts"]] == ["Tolerance is EUR 1.00."]
    assert open_items
    assert "Confirmed source kept" in open_items[0]["description"]


def test_same_rank_keeps_both_and_opens_item() -> None:
    first = _model("C6", "Tolerance is EUR 1.00.", 0)
    second = _model("C6", "Tolerance is EUR 0.50.", 1)
    buckets, open_items = merge_knowledge_models([first, second])
    statements = {item["statement"] for item in buckets["facts"]}
    assert statements == {"Tolerance is EUR 1.00.", "Tolerance is EUR 0.50."}
    assert open_items
    assert "both statements are kept" in open_items[0]["description"]


def test_matching_statements_do_not_create_open_item() -> None:
    first = _model("C5", "The process uses the ERP.", 0)
    second = _model("C8", "The process uses the ERP.", 1)
    buckets, open_items = merge_knowledge_models([first, second])
    assert len(buckets["facts"]) == 1
    assert open_items == []


def test_assembly_surfaces_conflict_as_open_item() -> None:
    skeleton = assemble_from_knowledge(
        [
            _model("C5", "Tolerance is EUR 1.00.", 0),
            _model("C8", "Tolerance is EUR 0.50.", 1),
        ],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
    )
    assert "EUR 0.50" in skeleton["facts"][0]
    assert any("EUR 1.00" in item["description"] for item in skeleton["open_items"])
