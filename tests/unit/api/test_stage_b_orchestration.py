from __future__ import annotations

from uuid import UUID

import pytest

from app.services import stage_b_orchestration
from app.services.framework_stub_template import load_framework_stub_template
from services.presentation.planner import PresentationPlannerError
from services.slides.content_generation.group_b.common import (
    GroupBContentGenerationError,
)

OPPORTUNITY_ID = UUID("11111111-1111-4111-8111-111111111111")


def _confirmed_framework() -> dict:
    framework = load_framework_stub_template(OPPORTUNITY_ID)
    framework["status"] = "confirmed"
    return framework


def test_planning_does_not_persist_raw_fixture_after_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        stage_b_orchestration.FixturePlanningClient,
        "complete_planning",
        lambda *_args, **_kwargs: {"schema_version": "1.0", "slides": []},
    )

    with pytest.raises(PresentationPlannerError):
        stage_b_orchestration.plan_json_from_confirmed_framework(_confirmed_framework())


def test_group_b_does_not_persist_raw_fixture_after_generation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        stage_b_orchestration,
        "_group_b_fixture_generator",
        lambda _layout_id: lambda _request: {"layoutId": "PROCESS_FLOW_01"},
    )

    with pytest.raises(GroupBContentGenerationError):
        stage_b_orchestration.build_slide_spec_for_planned_slide(
            planned={
                "order": 4,
                "layoutId": "PROCESS_FLOW_01",
                "frameworkReferences": ["chapter_2", "chapter_4"],
            },
            framework_json=_confirmed_framework(),
        )


@pytest.mark.parametrize(
    ("layout_id", "references", "required_field"),
    [
        ("ARCHITECTURE_01", ["chapter_6", "chapter_7"], "components"),
        ("COMPLIANCE_01", ["chapter_8"], "items"),
        ("SUCCESS_METRICS_01", ["chapter_3", "chapter_9"], "criteria"),
        ("OPEN_QUESTIONS_01", ["chapter_11"], "left"),
        ("NEXT_STEPS_01", ["chapter_13"], "steps"),
    ],
)
def test_group_c_layouts_use_owner_generators(
    layout_id: str,
    references: list[str],
    required_field: str,
) -> None:
    spec = stage_b_orchestration.build_slide_spec_for_planned_slide(
        planned={
            "order": 6,
            "layoutId": layout_id,
            "frameworkReferences": references,
        },
        framework_json=_confirmed_framework(),
    )

    assert spec["layoutId"] == layout_id
    assert spec["slideId"] == "slide_06"
    assert spec[required_field]
