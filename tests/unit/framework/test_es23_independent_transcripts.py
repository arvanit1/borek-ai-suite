"""Independent ES-23 transcripts — fixed wording, KM carries typed metrics (ES-5 shape)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.framework.assembly import assemble_from_knowledge
from services.framework.pipeline import generate_customer_framework, run_engines

ROOT = Path(__file__).resolve().parents[3]
TRANSCRIPTS = ROOT / "sample_transcripts"


def _ref(turn: int, *, speaker: str = "Client") -> list[dict]:
    return [{"conversation_id": "C1", "speaker_role": speaker, "excerpt_pointer": f"turn:{turn}"}]


def _fact(
    statement: str,
    *,
    turn: int = 1,
    origin: str = "SOURCE_FACT",
    confidence: str = "high",
    metric: dict | None = None,
    speaker: str = "Client",
) -> dict:
    entry = {
        "statement": statement,
        "source_refs": _ref(turn, speaker=speaker),
        "origin": origin,
        "confidence": confidence,
    }
    if metric is not None:
        entry["metric"] = metric
    return entry


def _requirement(
    statement: str,
    *,
    turn: int = 2,
    metric: dict | None = None,
) -> dict:
    return _fact(statement, turn=turn, origin="USER_INPUT", confidence="high", metric=metric)


def _empty_model(*, facts: list[dict], requirements: list[dict] | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "prompt_version": "framework-extraction:v1",
        "transcript_id": "T-TEST",
        "conversation_id": "C1",
        "facts": facts,
        "stated_requirements": requirements or [],
        "constraints": [],
        "named_systems": [],
        "named_rules": [],
        "named_exceptions": [],
        "people_and_roles": [],
        "timeline_mentions": [],
        "risks": [],
        "unknowns": [],
    }


INDEPENDENT_CASES = [
    pytest.param(
        "es23_independent_invoice_ap.txt",
        _empty_model(
            facts=[
                _fact(
                    "We touch close to six hundred vendor invoices every four weeks.",
                    turn=1,
                    metric={"kind": "monthly_volume", "value": 600, "unit": "invoices/month"},
                ),
                _fact(
                    "Clerks spend 110 staff-hours on the matchable portion each month.",
                    turn=1,
                    metric={"kind": "automatable_hours_mo", "value": 110, "unit": "hours/month"},
                ),
                _fact("Mismatches run about 9 percent of the batch.", turn=1, metric={"kind": "exception_rate_pct", "value": 9}),
                _fact("Policy binder is on page 14.", turn=1),
                _requirement(
                    "Goal is to bring clerical load on matching down to 30 hours per month.",
                    turn=2,
                    metric={"kind": "target_remaining_hours_mo", "value": 30},
                ),
                _fact("Fully loaded clerk rate is 52 euros an hour.", turn=2, metric={"kind": "loaded_hourly_cost_eur", "value": 52}),
                _fact(
                    "Agent guessed 80 percent automation eventually.",
                    turn=3,
                    origin="AI_INFERENCE",
                    confidence="low",
                    speaker="Agent",
                    metric={"kind": "automation_rate", "value": 0.8},
                ),
            ]
        ),
        {
            "monthly_volume": 600,
            "automatable_hours_mo": 110,
            "target_remaining_hours_mo": 30,
            "loaded_hourly_cost_eur": 52,
            "hours_saved_mo": 80,
            "forbidden_in_ch9": ("14", "4421", "March"),
        },
        id="invoice_ap",
    ),
    pytest.param(
        "es23_independent_hr_onboarding.txt",
        _empty_model(
            facts=[
                _fact(
                    "Roughly 120 new hires land each quarter, so about 40 a month.",
                    turn=1,
                    metric={"kind": "monthly_volume", "value": 40, "unit": "hires/month"},
                ),
                _fact(
                    "Onboarding coordinators log 180 hours monthly on repeatable paperwork.",
                    turn=1,
                    metric={"kind": "automatable_hours_mo", "value": 180},
                ),
                _fact("Incomplete files are 15 percent of cases.", turn=1, metric={"kind": "exception_rate_pct", "value": 15}),
                _requirement(
                    "We want coordinator effort under 50 hours within six months.",
                    turn=2,
                    metric={"kind": "target_remaining_hours_mo", "value": 50},
                ),
                _fact(
                    "Blended HR hourly is 35 euros loaded for your business case.",
                    turn=2,
                    metric={"kind": "loaded_hourly_cost_eur", "value": 35},
                ),
                _fact(
                    "Maybe 70 percent of packets could be straight-through.",
                    turn=3,
                    origin="AI_INFERENCE",
                    confidence="medium",
                ),
            ]
        ),
        {
            "monthly_volume": 40,
            "automatable_hours_mo": 180,
            "target_remaining_hours_mo": 50,
            "loaded_hourly_cost_eur": 35,
            "hours_saved_mo": 130,
            "forbidden_in_ch9": ("2022", "555", "0192"),
        },
        id="hr_onboarding",
    ),
    pytest.param(
        "es23_independent_customer_refunds.txt",
        _empty_model(
            facts=[
                _fact(
                    "The portal sees 2,400 refund tickets monthly.",
                    turn=1,
                    metric={"kind": "monthly_volume", "value": 2400, "unit": "tickets/month"},
                ),
                _fact(
                    "Agents burn 320 hours on tier-one review work each month.",
                    turn=1,
                    metric={"kind": "automatable_hours_mo", "value": 320},
                ),
                _fact("Chargeback disputes are 6 percent of volume.", turn=1, metric={"kind": "exception_rate_pct", "value": 6}),
                _requirement(
                    "Target state is 90 hours of human touch after automation.",
                    turn=2,
                    metric={"kind": "target_remaining_hours_mo", "value": 90},
                ),
                _fact("Loaded agent cost is EUR 41 per hour.", turn=2, metric={"kind": "loaded_hourly_cost_eur", "value": 41}),
                _fact(
                    "Agent suggested 95 percent auto-approval would be optimistic.",
                    turn=3,
                    origin="AI_INFERENCE",
                    confidence="low",
                    speaker="Agent",
                ),
            ]
        ),
        {
            "monthly_volume": 2400,
            "automatable_hours_mo": 320,
            "target_remaining_hours_mo": 90,
            "loaded_hourly_cost_eur": 41,
            "hours_saved_mo": 230,
            "forbidden_in_ch9": ("8812",),
        },
        id="customer_refunds",
    ),
    pytest.param(
        "es23_independent_warehouse_returns.txt",
        _empty_model(
            facts=[
                _fact(
                    "Distribution handles 670 RMA units monthly.",
                    turn=1,
                    metric={"kind": "monthly_volume", "value": 670, "unit": "units/month"},
                ),
                _fact(
                    "Receiving spends 88 labor hours on inspection and relabeling each month.",
                    turn=1,
                    metric={"kind": "automatable_hours_mo", "value": 88},
                ),
                _fact("Damaged-on-arrival is 11 percent of returns.", turn=1, metric={"kind": "exception_rate_pct", "value": 11}),
                _requirement(
                    "Leadership wants inspection labor capped at 25 hours per month.",
                    turn=2,
                    metric={"kind": "target_remaining_hours_mo", "value": 25},
                ),
                _fact("Warehouse labor runs EUR 29 per hour loaded.", turn=2, metric={"kind": "loaded_hourly_cost_eur", "value": 29}),
                _fact(
                    "Eighty-five percent straight-through sounds plausible on paper.",
                    turn=3,
                    origin="AI_INFERENCE",
                    confidence="medium",
                ),
            ]
        ),
        {
            "monthly_volume": 670,
            "automatable_hours_mo": 88,
            "target_remaining_hours_mo": 25,
            "loaded_hourly_cost_eur": 29,
            "hours_saved_mo": 63,
            "forbidden_in_ch9": ("018", "2019"),
        },
        id="warehouse_returns",
    ),
]


@pytest.mark.parametrize("transcript_file,model,expected", INDEPENDENT_CASES)
def test_es23_independent_transcript_engine_inputs_and_chapter_9(
    transcript_file: str,
    model: dict,
    expected: dict,
) -> None:
    transcript_path = TRANSCRIPTS / transcript_file
    assert transcript_path.is_file(), f"Missing transcript fixture: {transcript_path}"
    assert transcript_path.read_text(encoding="utf-8")

    skeleton = assemble_from_knowledge([model], opportunity_id=f"OPP-{transcript_file}")
    inputs = skeleton["engine_inputs"]
    assert inputs["monthly_volume"] == expected["monthly_volume"]
    assert inputs["automatable_hours_mo"] == expected["automatable_hours_mo"]
    assert inputs["target_remaining_hours_mo"] == expected["target_remaining_hours_mo"]
    assert inputs["loaded_hourly_cost_eur"] == expected["loaded_hourly_cost_eur"]

    business = run_engines(skeleton, overrides={})["business_case"]
    assert business["hours_saved_mo"] == expected["hours_saved_mo"]
    assert business["inputs"]["loaded_hourly_cost_eur"] == expected["loaded_hourly_cost_eur"]

    framework = generate_customer_framework(
        [model],
        opportunity_id=f"OPP-{transcript_file}",
        title_hint=transcript_file,
        use_llm=False,
    )
    ch9 = next(ch for ch in framework["chapters"] if str(ch.get("chapter_id")) == "9")
    ch9_blob = json.dumps(ch9, ensure_ascii=False)
    assert str(expected["hours_saved_mo"]) in ch9_blob
    for token in expected["forbidden_in_ch9"]:
        assert token not in ch9_blob, f"decoy or inferred token {token!r} leaked into ch9"


def test_es7_ai_inferred_metric_does_not_feed_business_case() -> None:
    model = _empty_model(
        facts=[
            _fact(
                "Process about 500 cases per month.",
                metric={"kind": "monthly_volume", "value": 500},
            ),
            _fact(
                "Repeatable work is 60 hours per month.",
                metric={"kind": "automatable_hours_mo", "value": 60},
            ),
            _requirement("Target remaining effort is 10 hours per month.", metric={"kind": "target_remaining_hours_mo", "value": 10}),
            _fact(
                "Loaded cost is EUR 40 per hour.",
                metric={"kind": "loaded_hourly_cost_eur", "value": 40},
            ),
            _fact(
                "Automation could reach 90 percent.",
                origin="AI_INFERENCE",
                confidence="low",
                metric={"kind": "automation_rate", "value": 0.9},
            ),
        ]
    )
    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-AI-INF")
    assert skeleton["engine_inputs"]["automation_rate"] is None
    assert skeleton["engine_inputs"]["monthly_volume"] == 500
    assert any("AI-inferred financial figure" in item["description"] for item in skeleton["open_items"])
    business = run_engines(skeleton, overrides={})["business_case"]
    assert business["inputs"]["automation_rate"] == pytest.approx(50 / 60, rel=1e-4)
    assert business["inputs"]["automation_rate"] != 0.9


def test_es23_team_hours_metric_maps_to_automatable_when_scoped() -> None:
    """Live ES-5 often emits team_hours_mo for matchable/inspection effort — harvest must still fill Ch.9."""
    model = {
        "conversation_id": "C1",
        "facts": [
            _fact(
                "Distribution handles 670 RMA units monthly.",
                metric={"kind": "monthly_volume", "value": 670},
            ),
            _fact(
                "Receiving spends 88 labor hours on inspection and relabeling each month.",
                metric={"kind": "team_hours_mo", "value": 88, "unit": "hours"},
            ),
            _fact("Warehouse labor runs EUR 29 per hour loaded.", metric={"kind": "loaded_hourly_cost_eur", "value": 29}),
        ],
        "stated_requirements": [
            _requirement(
                "Leadership wants inspection labor capped at 25 hours per month.",
                metric={"kind": "target_remaining_hours_mo", "value": 25},
            ),
        ],
        "constraints": [],
        "named_systems": [],
        "named_rules": [],
        "named_exceptions": [],
        "people_and_roles": [],
        "timeline_mentions": [],
        "risks": [],
        "unknowns": [],
    }
    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-WARE-LIVE")
    assert skeleton["engine_inputs"]["automatable_hours_mo"] == 88.0
    assert "automatable_hours_mo" not in skeleton["engine_inputs"]["unresolved_fields"]
    business = run_engines(skeleton, overrides={})["business_case"]
    assert business["inputs"]["automatable_hours_mo"] == 88.0
    assert business["hours_saved_mo"] == 63


def test_es7_medium_confidence_user_input_does_not_feed_financial_harvest() -> None:
    model = _empty_model(
        facts=[
            _fact(
                "About 500 cases per month.",
                origin="USER_INPUT",
                confidence="medium",
                metric={"kind": "monthly_volume", "value": 500},
            ),
        ]
    )
    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-MED")
    assert skeleton["engine_inputs"]["monthly_volume"] is None


def test_es7_low_confidence_gut_estimate_does_not_feed_automation_rate() -> None:
    model = _empty_model(
        facts=[
            _fact("Process about 500 cases per month.", metric={"kind": "monthly_volume", "value": 500}),
            _fact("Repeatable work is 60 hours per month.", metric={"kind": "automatable_hours_mo", "value": 60}),
            _requirement("Target remaining effort is 10 hours per month.", metric={"kind": "target_remaining_hours_mo", "value": 10}),
            _fact("Loaded cost is EUR 40 per hour.", metric={"kind": "loaded_hourly_cost_eur", "value": 40}),
            _fact(
                "Maybe 70 percent of packets could be straight-through — gut feeling, not a signed KPI.",
                confidence="low",
                metric={"kind": "automation_rate", "value": 0.7},
            ),
        ]
    )
    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-GUT")
    assert skeleton["engine_inputs"]["automation_rate"] is None
    assert any("Low-confidence estimate" in item["description"] for item in skeleton["open_items"])
