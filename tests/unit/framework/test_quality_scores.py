"""ES-11 / M2 — golden scores 85 / 82 / 94."""

from __future__ import annotations

from services.framework.business_case import compute_business_case
from services.framework.estimation import estimate_effort
from services.framework.quality_scores import (
    assemble_quality_scores,
    green_light,
    score_build_readiness,
    score_conversation_quality,
    score_opportunity,
)


def test_opportunity_rating_golden_is_85() -> None:
    result = score_opportunity(
        hours_mo=306,
        timeline_weeks=3.0,
        strategic_fit_level=3,
        feasibility_level=2,
        risk_inverted_level=2,
    )
    assert result["score"] == 85
    assert result["dims"]["impact"] == 100
    assert result["dims"]["speed"] == 100
    assert "hours_mo" in result["inputs"]


def test_conversation_quality_golden_is_82_strong() -> None:
    result = score_conversation_quality(
        result_quality=90,
        information_richness=85,
        engagement=65,
    )
    assert result["score"] == 82
    assert result["band"] == "strong"


def test_build_readiness_golden_is_94_ready_to_build() -> None:
    result = score_build_readiness(
        has_aim_metric=True,
        functional_spec_complete=True,
        has_sample=True,
        intake_read_available=True,
        system_read_available=True,
        system_write_available=False,
        data_compliance_complete=True,
        estimate_complete=True,
        business_case_complete=True,
        acceptance_complete=True,
        blocker_open_questions=0,
    )
    assert result["score"] == 94
    assert result["band"] == "ready_to_build"
    assert result["blocks"]["integrations"] == 12


def test_quality_scores_bundle_has_rationale_for_each_gate() -> None:
    opportunity = score_opportunity(hours_mo=306, timeline_weeks=3, strategic_fit_level=3, feasibility_level=2, risk_inverted_level=2)
    conversation = score_conversation_quality(result_quality=90, information_richness=85, engagement=65)
    readiness = score_build_readiness(
        has_aim_metric=True,
        functional_spec_complete=True,
        has_sample=True,
        intake_read_available=True,
        system_read_available=True,
        system_write_available=False,
        data_compliance_complete=True,
        estimate_complete=True,
        business_case_complete=True,
        acceptance_complete=True,
        blocker_open_questions=0,
    )
    bundled = assemble_quality_scores(opportunity, conversation, readiness)
    assert bundled["opportunity_rating"] == 85
    assert bundled["conversation_quality"] == 82
    assert bundled["build_readiness"] == 94
    for key in ("opportunity_rating", "conversation_quality", "build_readiness"):
        line = bundled["rationale"][key]
        assert line
        assert "\n" not in line
        assert f"{bundled[key]}/100" in line


def test_green_light_requires_all_three_usable_gates() -> None:
    assert green_light(85, 82, 94) is True
    assert green_light(70, 82, 94) is False
    assert green_light(85, 70, 94) is False
    assert green_light(85, 82, 70) is False


def test_assembled_scores_clamp_to_0_100() -> None:
    bundled = assemble_quality_scores(
        {"score": 140, "inputs": {"hours_mo": 10, "timeline_weeks": 12}},
        {"score": -4, "band": "needs_human_followup"},
        {"score": 50, "band": "not_ready"},
    )
    assert bundled["opportunity_rating"] == 100
    assert bundled["conversation_quality"] == 0
    assert bundled["build_readiness"] == 50
    assert "100/100" in bundled["rationale"]["opportunity_rating"]


def test_estimate_golden_t2_three_weeks_15000() -> None:
    result = estimate_effort(
        archetype="system_to_system",
        step_count=5,
        system_count=2,
        rule_count=6,
        hard_integration_count=0,
        data_readiness="ready",
        reuse=["library_component"],
        builder_count=1,
    )
    assert result["tier"] == "T2"
    assert result["effort_weeks"]["likely"] == 3.0
    assert result["effort_weeks"]["min"] == 2.1
    assert result["effort_weeks"]["max"] == 3.9
    assert result["build_cost_eur"] == 15000


def test_business_case_golden_figures() -> None:
    result = compute_business_case(
        automatable_hours_mo=73,
        monthly_volume=3000,
        loaded_hourly_cost_eur=45,
        automation_rate=0.85,
        build_cost_eur=15000,
        archetype="system_to_system",
    )
    assert result["hours_saved_mo"] == 62
    assert result["gross_eur_mo"] == 2800
    assert result["run_cost_eur_mo"] == 400
    assert result["net_eur_mo"] == 2400
    assert result["payback_months"] == 6.3
    assert result["roi_36m_pct"] == 476
    assert set(result["sensitivity"]) == {"low", "expected", "high"}
    assert result["sensitivity"]["low"]["automation_rate"] == 0.70
    assert result["sensitivity"]["high"]["automation_rate"] == 0.92
