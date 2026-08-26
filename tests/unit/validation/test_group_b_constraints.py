"""JJ-10: Group B content-limit definitions and AT-7 registration tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.slides.group_b_constraints import (
    CONFIG_PATH,
    GROUP_B_LAYOUT_IDS,
    load_group_b_constraint_configs,
    register_group_b_constraints,
)
from services.validation.constraint_validator import (
    ConstraintViolation,
    LayoutConstraintRegistry,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_b"
SCHEMA_DIR = ROOT / "packages" / "contracts" / "slide_spec" / "group_b"

FIXTURE_NAMES = {
    "PROCESS_FLOW_01": "process_flow_01.minimal.json",
    "TIMELINE_01": "timeline_01.minimal.json",
    "MILESTONES_01": "milestones_01.minimal.json",
    "TEAM_FTE_01": "team_fte_01.minimal.json",
}

SCHEMA_NAMES = {
    "PROCESS_FLOW_01": "process_flow_01.schema.json",
    "TIMELINE_01": "timeline_01.schema.json",
    "MILESTONES_01": "milestones_01.schema.json",
    "TEAM_FTE_01": "team_fte_01.schema.json",
}


@pytest.fixture(scope="module")
def configs() -> dict[str, dict]:
    return load_group_b_constraint_configs()


@pytest.fixture(scope="module")
def registry() -> LayoutConstraintRegistry:
    return register_group_b_constraints(LayoutConstraintRegistry())


def _payload(layout_id: str) -> dict:
    return json.loads((FIXTURE_DIR / FIXTURE_NAMES[layout_id]).read_text(encoding="utf-8"))


def _at_all_limits(layout_id: str) -> dict:
    payload = _payload(layout_id)
    payload.update(sectionLabel="S" * 32, title="T" * 72, subtitle="U" * 100)
    if layout_id == "PROCESS_FLOW_01":
        payload["phases"] = [
            {"number": index + 1, "name": "N" * 32, "description": "D" * 80}
            for index in range(8)
        ]
    elif layout_id == "TIMELINE_01":
        payload["phases"] = [
            {"id": f"p{index}", "name": "N" * 28, "description": "D" * 75}
            for index in range(8)
        ]
        payload["milestones"] = [
            {
                "id": f"m{index}",
                "name": "M" * 32,
                "phaseId": f"p{index}",
                "date": "D" * 24,
                "description": "X" * 80,
            }
            for index in range(8)
        ]
    elif layout_id == "MILESTONES_01":
        payload["milestones"] = [
            {"name": "N" * 40, "description": "D" * 90, "date": "W" * 24}
            for _ in range(8)
        ]
    elif layout_id == "TEAM_FTE_01":
        payload["roles"] = [
            {"role": "R" * 32, "fte": "F" * 16, "responsibility": "C" * 80}
            for _ in range(6)
        ]
        payload["summary"] = [{"label": "L" * 24, "value": "V" * 16} for _ in range(4)]
    else:  # pragma: no cover
        raise AssertionError(f"Unsupported test layout {layout_id}")
    return payload


def _violations(registry: LayoutConstraintRegistry, payload: dict) -> list[ConstraintViolation]:
    return registry.collect_violations(payload)


def _assert_limit_violation(
    registry: LayoutConstraintRegistry,
    payload: dict,
    *,
    path: str,
    code: str,
    limit: int,
) -> None:
    matches = [
        violation
        for violation in _violations(registry, payload)
        if violation.path == path and violation.code == code and violation.limit == limit
    ]
    assert matches, f"missing {code} violation at {path} with limit {limit}"


def test_jj10_config_file_is_json_compatible_yaml() -> None:
    assert CONFIG_PATH.suffix == ".yaml"
    document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert document["ticket"] == "JJ-10"
    assert document["limit_classification"] == "CALIBRATED"


def test_jj10_defines_and_registers_exactly_four_group_b_layouts(
    configs: dict[str, dict], registry: LayoutConstraintRegistry
) -> None:
    assert tuple(configs) == GROUP_B_LAYOUT_IDS
    for layout_id in GROUP_B_LAYOUT_IDS:
        assert registry.get(layout_id) == configs[layout_id]


@pytest.mark.parametrize("layout_id", GROUP_B_LAYOUT_IDS)
def test_jj10_only_constrains_fields_present_in_layout_schema(
    layout_id: str, configs: dict[str, dict]
) -> None:
    schema = json.loads((SCHEMA_DIR / SCHEMA_NAMES[layout_id]).read_text(encoding="utf-8"))
    assert set(configs[layout_id]["properties"]) <= set(schema["properties"])


@pytest.mark.parametrize("layout_id", GROUP_B_LAYOUT_IDS)
def test_jj10_minimal_group_b_fixtures_pass(
    layout_id: str, registry: LayoutConstraintRegistry
) -> None:
    registry.validate_slide_spec(_payload(layout_id))


@pytest.mark.parametrize("layout_id", GROUP_B_LAYOUT_IDS)
def test_jj10_exactly_at_every_calibrated_limit_passes(
    layout_id: str, registry: LayoutConstraintRegistry
) -> None:
    registry.validate_slide_spec(_at_all_limits(layout_id))


@pytest.mark.parametrize(
    ("layout_id", "field", "maximum", "prototype"),
    [
        (
            "PROCESS_FLOW_01",
            "phases",
            8,
            {"number": 1, "name": "Receive", "description": "Mailbox intake"},
        ),
        (
            "TIMELINE_01",
            "phases",
            8,
            {"id": "p1", "name": "Discover", "description": "Confirm access"},
        ),
        (
            "TIMELINE_01",
            "milestones",
            8,
            {"id": "m1", "name": "Access", "phaseId": "p1"},
        ),
        (
            "MILESTONES_01",
            "milestones",
            8,
            {"name": "Access confirmed", "description": "Read-only data"},
        ),
        (
            "TEAM_FTE_01",
            "roles",
            6,
            {"role": "Owner", "fte": "0.3", "responsibility": "Approvals"},
        ),
    ],
)
def test_jj10_item_count_limits(
    layout_id: str,
    field: str,
    maximum: int,
    prototype: object,
    registry: LayoutConstraintRegistry,
) -> None:
    payload = _payload(layout_id)
    payload[field] = [copy.deepcopy(prototype) for _ in range(maximum)]
    registry.validate_slide_spec(payload)

    payload[field].append(copy.deepcopy(prototype))
    _assert_limit_violation(
        registry,
        payload,
        path=field,
        code="max_items",
        limit=maximum,
    )


def test_jj10_process_flow_phase_name_limit(registry: LayoutConstraintRegistry) -> None:
    payload = _payload("PROCESS_FLOW_01")
    payload["phases"][0]["name"] = "N" * 33
    _assert_limit_violation(
        registry,
        payload,
        path="phases[0].name",
        code="max_length",
        limit=32,
    )


def test_jj10_timeline_phase_name_follows_section_15_example(
    registry: LayoutConstraintRegistry,
) -> None:
    payload = _payload("TIMELINE_01")
    payload["phases"][0]["name"] = "N" * 29
    _assert_limit_violation(
        registry,
        payload,
        path="phases[0].name",
        code="max_length",
        limit=28,
    )


def test_jj10_team_member_responsibility_limit(registry: LayoutConstraintRegistry) -> None:
    payload = _payload("TEAM_FTE_01")
    payload["roles"][0]["responsibility"] = "R" * 81
    _assert_limit_violation(
        registry,
        payload,
        path="roles[0].responsibility",
        code="max_length",
        limit=80,
    )
