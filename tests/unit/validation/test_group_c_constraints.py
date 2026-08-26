"""MS-12: Group C content-limit definitions and AT-7 registration tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.slides.group_c_constraints import (
    CONFIG_PATH,
    GROUP_C_LAYOUT_IDS,
    load_group_c_constraint_configs,
    register_group_c_constraints,
)
from services.validation.constraint_validator import (
    ConstraintViolation,
    LayoutConstraintRegistry,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec"
SCHEMA_DIR = ROOT / "packages" / "contracts" / "slide_spec" / "group_c"

FIXTURE_NAMES = {
    "ARCHITECTURE_01": "architecture_01.minimal.json",
    "COMPLIANCE_01": "compliance_01.minimal.json",
    "SUCCESS_METRICS_01": "success_metrics_01.minimal.json",
    "OPEN_QUESTIONS_01": "open_questions_01.minimal.json",
    "NEXT_STEPS_01": "next_steps_01.minimal.json",
}

SCHEMA_NAMES = {
    "ARCHITECTURE_01": "architecture_01.schema.json",
    "COMPLIANCE_01": "compliance_01.schema.json",
    "SUCCESS_METRICS_01": "success_metrics_01.schema.json",
    "OPEN_QUESTIONS_01": "open_questions_01.schema.json",
    "NEXT_STEPS_01": "next_steps_01.schema.json",
}

ARCHITECTURE_COMPONENT = {
    "number": 1,
    "title": "Node",
    "description": "A connected system",
}
COMPLIANCE_ITEM = {"icon": "lock", "text": "Read-only mailbox access"}
SUCCESS_CRITERION = {
    "title": "Auto-match rate",
    "description": "Invoices matched without a manual check",
}
NEXT_STEP = {"number": 1, "text": "Workshop exception rules"}


@pytest.fixture(scope="module")
def configs() -> dict[str, dict]:
    return load_group_c_constraint_configs()


@pytest.fixture(scope="module")
def registry() -> LayoutConstraintRegistry:
    return register_group_c_constraints(LayoutConstraintRegistry())


def _payload(layout_id: str) -> dict:
    return json.loads((FIXTURE_DIR / FIXTURE_NAMES[layout_id]).read_text(encoding="utf-8"))


def _at_all_limits(layout_id: str) -> dict:
    payload = _payload(layout_id)
    if layout_id == "ARCHITECTURE_01":
        payload.update(sectionLabel="S" * 32, title="T" * 72, subtitle="U" * 100)
        payload["components"] = [
            {"number": index + 1, "title": "N" * 40, "description": "D" * 100}
            for index in range(8)
        ]
    elif layout_id == "COMPLIANCE_01":
        payload.update(sectionLabel="S" * 32, title="T" * 72, subtitle="U" * 100)
        payload["items"] = [{"icon": "I" * 24, "text": "X" * 100} for _ in range(6)]
    elif layout_id == "SUCCESS_METRICS_01":
        payload.update(sectionLabel="S" * 32, title="T" * 72, subtitle="U" * 100)
        payload["criteria"] = [
            {"title": "H" * 48, "description": "D" * 160} for _ in range(6)
        ]
    elif layout_id == "OPEN_QUESTIONS_01":
        payload.update(sectionLabel="S" * 32, title="T" * 72, subtitle="U" * 100)
        column = {"heading": "H" * 40, "items": ["Q" * 120 for _ in range(6)]}
        payload["left"] = copy.deepcopy(column)
        payload["right"] = copy.deepcopy(column)
    elif layout_id == "NEXT_STEPS_01":
        payload.update(sectionLabel="S" * 32, title="T" * 72, subtitle="U" * 100)
        payload["checklist"] = ["C" * 72 for _ in range(6)]
        payload["steps"] = [
            {"number": index + 1, "text": "S" * 100} for index in range(6)
        ]
    else:  # pragma: no cover - guarded by GROUP_C_LAYOUT_IDS
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


def test_ms12_config_file_is_json_compatible_yaml() -> None:
    assert CONFIG_PATH.suffix == ".yaml"
    document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert document["ticket"] == "MS-12"
    assert document["limit_classification"] == "CALIBRATED"


def test_ms12_defines_and_registers_exactly_five_group_c_layouts(
    configs: dict[str, dict], registry: LayoutConstraintRegistry
) -> None:
    assert tuple(configs) == GROUP_C_LAYOUT_IDS
    for layout_id in GROUP_C_LAYOUT_IDS:
        assert registry.get(layout_id) == configs[layout_id]


@pytest.mark.parametrize("layout_id", GROUP_C_LAYOUT_IDS)
def test_ms12_only_constrains_fields_present_in_layout_schema(
    layout_id: str, configs: dict[str, dict]
) -> None:
    schema = json.loads((SCHEMA_DIR / SCHEMA_NAMES[layout_id]).read_text(encoding="utf-8"))
    assert set(configs[layout_id]["properties"]) <= set(schema["properties"])


@pytest.mark.parametrize("layout_id", GROUP_C_LAYOUT_IDS)
def test_ms12_minimal_group_c_fixtures_pass(
    layout_id: str, registry: LayoutConstraintRegistry
) -> None:
    registry.validate_slide_spec(_payload(layout_id))


@pytest.mark.parametrize("layout_id", GROUP_C_LAYOUT_IDS)
def test_ms12_exactly_at_every_calibrated_limit_passes(
    layout_id: str, registry: LayoutConstraintRegistry
) -> None:
    registry.validate_slide_spec(_at_all_limits(layout_id))


@pytest.mark.parametrize(
    ("layout_id", "limit"),
    [
        ("ARCHITECTURE_01", 72),
        ("COMPLIANCE_01", 72),
        ("SUCCESS_METRICS_01", 72),
        ("OPEN_QUESTIONS_01", 72),
        ("NEXT_STEPS_01", 72),
    ],
)
def test_ms12_one_character_over_title_limit_fails(
    layout_id: str, limit: int, registry: LayoutConstraintRegistry
) -> None:
    payload = _payload(layout_id)
    payload["title"] = "T" * (limit + 1)
    _assert_limit_violation(registry, payload, path="title", code="max_length", limit=limit)


def test_ms12_architecture_node_text_limits(registry: LayoutConstraintRegistry) -> None:
    payload = _payload("ARCHITECTURE_01")
    payload["components"][0]["title"] = "X" * 41
    _assert_limit_violation(
        registry, payload, path="components[0].title", code="max_length", limit=40
    )

    payload = _payload("ARCHITECTURE_01")
    payload["components"][0]["description"] = "X" * 101
    _assert_limit_violation(
        registry, payload, path="components[0].description", code="max_length", limit=100
    )


def test_ms12_compliance_card_text_limit_fails(registry: LayoutConstraintRegistry) -> None:
    payload = _payload("COMPLIANCE_01")
    payload["items"][0]["text"] = "X" * 101
    _assert_limit_violation(
        registry, payload, path="items[0].text", code="max_length", limit=100
    )


def test_ms12_success_metric_text_limits_fail(registry: LayoutConstraintRegistry) -> None:
    payload = _payload("SUCCESS_METRICS_01")
    payload["criteria"][0]["title"] = "X" * 49
    _assert_limit_violation(
        registry, payload, path="criteria[0].title", code="max_length", limit=48
    )

    payload = _payload("SUCCESS_METRICS_01")
    payload["criteria"][0]["description"] = "X" * 161
    _assert_limit_violation(
        registry, payload, path="criteria[0].description", code="max_length", limit=160
    )


@pytest.mark.parametrize("column", ["left", "right"])
def test_ms12_open_questions_item_limit_fails(
    column: str, registry: LayoutConstraintRegistry
) -> None:
    payload = _payload("OPEN_QUESTIONS_01")
    payload[column]["items"][0] = "X" * 121
    _assert_limit_violation(
        registry,
        payload,
        path=f"{column}.items[0]",
        code="max_length",
        limit=120,
    )


def test_ms12_next_steps_text_limits_fail(registry: LayoutConstraintRegistry) -> None:
    payload = _payload("NEXT_STEPS_01")
    payload["checklist"][0] = "X" * 73
    _assert_limit_violation(
        registry, payload, path="checklist[0]", code="max_length", limit=72
    )

    payload = _payload("NEXT_STEPS_01")
    payload["steps"][0]["text"] = "X" * 101
    _assert_limit_violation(
        registry, payload, path="steps[0].text", code="max_length", limit=100
    )


@pytest.mark.parametrize(
    ("layout_id", "field", "minimum", "prototype"),
    [
        ("ARCHITECTURE_01", "components", 2, ARCHITECTURE_COMPONENT),
        ("COMPLIANCE_01", "items", 1, COMPLIANCE_ITEM),
        ("SUCCESS_METRICS_01", "criteria", 1, SUCCESS_CRITERION),
        ("NEXT_STEPS_01", "checklist", 1, "Confirm mailbox access path"),
        ("NEXT_STEPS_01", "steps", 1, NEXT_STEP),
    ],
)
def test_ms12_minimum_item_count_passes(
    layout_id: str,
    field: str,
    minimum: int,
    prototype: object,
    registry: LayoutConstraintRegistry,
) -> None:
    payload = _payload(layout_id)
    payload[field] = [copy.deepcopy(prototype) for _ in range(minimum)]
    registry.validate_slide_spec(payload)


@pytest.mark.parametrize(
    ("layout_id", "field", "maximum", "prototype"),
    [
        ("ARCHITECTURE_01", "components", 8, ARCHITECTURE_COMPONENT),
        ("COMPLIANCE_01", "items", 6, COMPLIANCE_ITEM),
        ("SUCCESS_METRICS_01", "criteria", 6, SUCCESS_CRITERION),
        ("NEXT_STEPS_01", "checklist", 6, "Confirm mailbox access path"),
        ("NEXT_STEPS_01", "steps", 6, NEXT_STEP),
    ],
)
def test_ms12_maximum_item_count_passes_and_one_over_fails(
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


def test_ms12_architecture_one_component_fails_minimum(
    registry: LayoutConstraintRegistry,
) -> None:
    payload = _payload("ARCHITECTURE_01")
    payload["components"] = [copy.deepcopy(ARCHITECTURE_COMPONENT)]
    _assert_limit_violation(registry, payload, path="components", code="min_items", limit=2)


@pytest.mark.parametrize(
    ("layout_id", "field", "minimum"),
    [
        ("COMPLIANCE_01", "items", 1),
        ("SUCCESS_METRICS_01", "criteria", 1),
        ("NEXT_STEPS_01", "checklist", 1),
        ("NEXT_STEPS_01", "steps", 1),
    ],
)
def test_ms12_zero_items_fails_minimum(
    layout_id: str, field: str, minimum: int, registry: LayoutConstraintRegistry
) -> None:
    payload = _payload(layout_id)
    payload[field] = []
    _assert_limit_violation(registry, payload, path=field, code="min_items", limit=minimum)


def test_ms12_open_questions_column_item_counts_are_independent(
    registry: LayoutConstraintRegistry,
) -> None:
    payload = _payload("OPEN_QUESTIONS_01")
    payload["left"]["items"] = ["Question" for _ in range(6)]
    payload["right"]["items"] = ["Assumption"]
    registry.validate_slide_spec(payload)

    payload["left"]["items"] = ["Question"]
    payload["right"]["items"] = ["Assumption" for _ in range(6)]
    registry.validate_slide_spec(payload)


def test_ms12_open_questions_empty_column_items_fail(
    registry: LayoutConstraintRegistry,
) -> None:
    payload = _payload("OPEN_QUESTIONS_01")
    payload["left"]["items"] = []
    _assert_limit_violation(registry, payload, path="left.items", code="min_items", limit=1)


@pytest.mark.parametrize("layout_id", GROUP_C_LAYOUT_IDS)
def test_ms12_validation_leaves_source_chapter_ids_unchanged(
    layout_id: str, registry: LayoutConstraintRegistry
) -> None:
    payload = _payload(layout_id)
    before = copy.deepcopy(payload)
    registry.validate_slide_spec(payload)
    assert payload == before
    assert payload["sourceChapterIds"] == before["sourceChapterIds"]


def test_ms12_registration_is_additive_with_group_a() -> None:
    from services.slides.group_a_constraints import (
        GROUP_A_LAYOUT_IDS,
        register_group_a_constraints,
    )

    registry = register_group_c_constraints(
        register_group_a_constraints(LayoutConstraintRegistry())
    )
    for layout_id in GROUP_A_LAYOUT_IDS:
        assert registry.get(layout_id) is not None
    for layout_id in GROUP_C_LAYOUT_IDS:
        assert registry.get(layout_id) is not None
