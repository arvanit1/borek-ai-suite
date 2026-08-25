"""BT-15: Group A content-limit definitions and AT-7 registration tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.slides.group_a_constraints import (
    CONFIG_PATH,
    GROUP_A_LAYOUT_IDS,
    load_group_a_constraint_configs,
    register_group_a_constraints,
)
from services.validation.constraint_validator import (
    ConstraintViolation,
    LayoutConstraintRegistry,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a"
SCHEMA_DIR = ROOT / "packages" / "contracts" / "slide_spec" / "group_a"

FIXTURE_NAMES = {
    "COVER_01": "cover_01.minimal.json",
    "CONTEXT_01": "context_01.minimal.json",
    "PROBLEM_SOLUTION_01": "problem_solution_01.minimal.json",
    "SCOPE_01": "scope_01.minimal.json",
    "REQUIREMENTS_MATRIX_01": "requirements_matrix_01.minimal.json",
}

SCHEMA_NAMES = {
    "COVER_01": "cover_01.schema.json",
    "CONTEXT_01": "context_01.schema.json",
    "PROBLEM_SOLUTION_01": "problem_solution_01.schema.json",
    "SCOPE_01": "scope_01.schema.json",
    "REQUIREMENTS_MATRIX_01": "requirements_matrix_01.schema.json",
}


@pytest.fixture(scope="module")
def configs() -> dict[str, dict]:
    return load_group_a_constraint_configs()


@pytest.fixture(scope="module")
def registry() -> LayoutConstraintRegistry:
    return register_group_a_constraints(LayoutConstraintRegistry())


def _payload(layout_id: str) -> dict:
    return json.loads((FIXTURE_DIR / FIXTURE_NAMES[layout_id]).read_text(encoding="utf-8"))


def _at_all_limits(layout_id: str) -> dict:
    payload = _payload(layout_id)
    if layout_id == "COVER_01":
        payload.update(sectionLabel="S" * 40, title="T" * 60, subtitle="U" * 100)
        payload["statBadges"] = [
            {"value": "V" * 16, "label": "L" * 32} for _ in range(3)
        ]
    elif layout_id == "CONTEXT_01":
        payload.update(sectionLabel="S" * 32, title="T" * 72, subtitle="U" * 100)
        for field in ("problem", "solution", "currentState", "targetState"):
            payload[field] = {"title": "H" * 32, "description": "D" * 160}
    elif layout_id == "PROBLEM_SOLUTION_01":
        payload.update(sectionLabel="S" * 32, title="T" * 72, subtitle="U" * 100)
        for field in ("problem", "solution"):
            payload[field] = {"title": "H" * 48, "description": "D" * 220}
    elif layout_id == "SCOPE_01":
        payload.update(sectionLabel="S" * 32, title="T" * 72, subtitle="U" * 100)
        payload["included"] = ["I" * 72 for _ in range(7)]
        payload["later"] = ["L" * 72 for _ in range(5)]
    elif layout_id == "REQUIREMENTS_MATRIX_01":
        payload.update(sectionLabel="S" * 32, title="T" * 72, subtitle="U" * 100)
        payload["requirements"] = [
            {"category": "C" * 12, "title": "R" * 48, "status": "included"}
            for _ in range(6)
        ]
    else:  # pragma: no cover - guarded by GROUP_A_LAYOUT_IDS
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


def test_bt15_config_file_is_json_compatible_yaml() -> None:
    assert CONFIG_PATH.suffix == ".yaml"
    document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert document["ticket"] == "BT-15"
    assert document["limit_classification"] == "CALIBRATED"


def test_bt15_defines_and_registers_exactly_five_group_a_layouts(
    configs: dict[str, dict], registry: LayoutConstraintRegistry
) -> None:
    assert tuple(configs) == GROUP_A_LAYOUT_IDS
    for layout_id in GROUP_A_LAYOUT_IDS:
        assert registry.get(layout_id) == configs[layout_id]


@pytest.mark.parametrize("layout_id", GROUP_A_LAYOUT_IDS)
def test_bt15_only_constrains_fields_present_in_layout_schema(
    layout_id: str, configs: dict[str, dict]
) -> None:
    schema = json.loads((SCHEMA_DIR / SCHEMA_NAMES[layout_id]).read_text(encoding="utf-8"))
    assert set(configs[layout_id]["properties"]) <= set(schema["properties"])


@pytest.mark.parametrize("layout_id", GROUP_A_LAYOUT_IDS)
def test_bt15_minimal_group_a_fixtures_pass(
    layout_id: str, registry: LayoutConstraintRegistry
) -> None:
    registry.validate_slide_spec(_payload(layout_id))


@pytest.mark.parametrize("layout_id", GROUP_A_LAYOUT_IDS)
def test_bt15_exactly_at_every_calibrated_limit_passes(
    layout_id: str, registry: LayoutConstraintRegistry
) -> None:
    registry.validate_slide_spec(_at_all_limits(layout_id))


@pytest.mark.parametrize(
    ("layout_id", "limit"),
    [
        ("COVER_01", 60),
        ("CONTEXT_01", 72),
        ("PROBLEM_SOLUTION_01", 72),
        ("SCOPE_01", 72),
        ("REQUIREMENTS_MATRIX_01", 72),
    ],
)
def test_bt15_one_character_over_title_limit_fails(
    layout_id: str, limit: int, registry: LayoutConstraintRegistry
) -> None:
    payload = _payload(layout_id)
    payload["title"] = "T" * (limit + 1)
    _assert_limit_violation(registry, payload, path="title", code="max_length", limit=limit)


def test_bt15_cover_subtitle_and_badge_text_limits(
    registry: LayoutConstraintRegistry,
) -> None:
    cases = [
        ("subtitle", 100),
        ("statBadges[0].value", 16),
        ("statBadges[0].label", 32),
    ]
    for path, limit in cases:
        payload = _payload("COVER_01")
        if path == "subtitle":
            payload["subtitle"] = "X" * (limit + 1)
        else:
            field = path.rsplit(".", 1)[1]
            payload["statBadges"][0][field] = "X" * (limit + 1)
        _assert_limit_violation(registry, payload, path=path, code="max_length", limit=limit)


@pytest.mark.parametrize(
    ("layout_id", "block", "field", "limit"),
    [
        ("CONTEXT_01", "problem", "title", 32),
        ("CONTEXT_01", "solution", "description", 160),
        ("CONTEXT_01", "currentState", "description", 160),
        ("CONTEXT_01", "targetState", "title", 32),
        ("PROBLEM_SOLUTION_01", "problem", "title", 48),
        ("PROBLEM_SOLUTION_01", "problem", "description", 220),
        ("PROBLEM_SOLUTION_01", "solution", "title", 48),
        ("PROBLEM_SOLUTION_01", "solution", "description", 220),
    ],
)
def test_bt15_one_character_over_nested_content_limit_fails(
    layout_id: str,
    block: str,
    field: str,
    limit: int,
    registry: LayoutConstraintRegistry,
) -> None:
    payload = _payload(layout_id)
    payload[block][field] = "X" * (limit + 1)
    _assert_limit_violation(
        registry,
        payload,
        path=f"{block}.{field}",
        code="max_length",
        limit=limit,
    )


@pytest.mark.parametrize("list_name", ["included", "later"])
def test_bt15_scope_long_list_item_fails(
    list_name: str, registry: LayoutConstraintRegistry
) -> None:
    payload = _payload("SCOPE_01")
    payload[list_name][0] = "X" * 73
    _assert_limit_violation(
        registry,
        payload,
        path=f"{list_name}[0]",
        code="max_length",
        limit=72,
    )


@pytest.mark.parametrize(("field", "limit"), [("category", 12), ("title", 48)])
def test_bt15_requirement_text_limit_fails(
    field: str, limit: int, registry: LayoutConstraintRegistry
) -> None:
    payload = _payload("REQUIREMENTS_MATRIX_01")
    payload["requirements"][0][field] = "X" * (limit + 1)
    _assert_limit_violation(
        registry,
        payload,
        path=f"requirements[0].{field}",
        code="max_length",
        limit=limit,
    )


@pytest.mark.parametrize(
    ("layout_id", "field", "minimum"),
    [
        ("COVER_01", "statBadges", 1),
        ("SCOPE_01", "included", 1),
        ("SCOPE_01", "later", 1),
        ("REQUIREMENTS_MATRIX_01", "requirements", 1),
    ],
)
def test_bt15_minimum_item_count_passes(
    layout_id: str, field: str, minimum: int, registry: LayoutConstraintRegistry
) -> None:
    payload = _payload(layout_id)
    payload[field] = payload[field][:minimum]
    registry.validate_slide_spec(payload)


@pytest.mark.parametrize(
    ("layout_id", "field", "maximum", "prototype"),
    [
        ("COVER_01", "statBadges", 3, {"value": "1", "label": "Badge"}),
        ("SCOPE_01", "included", 7, "Included item"),
        ("SCOPE_01", "later", 5, "Later item"),
        (
            "REQUIREMENTS_MATRIX_01",
            "requirements",
            6,
            {"category": "A", "title": "Requirement", "status": "included"},
        ),
    ],
)
def test_bt15_maximum_item_count_passes_and_one_over_fails(
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


@pytest.mark.parametrize(
    ("layout_id", "field"),
    [
        ("COVER_01", "statBadges"),
        ("SCOPE_01", "included"),
        ("SCOPE_01", "later"),
        ("REQUIREMENTS_MATRIX_01", "requirements"),
    ],
)
def test_bt15_zero_items_fails_minimum(
    layout_id: str, field: str, registry: LayoutConstraintRegistry
) -> None:
    payload = _payload(layout_id)
    payload[field] = []
    _assert_limit_violation(registry, payload, path=field, code="min_items", limit=1)


def test_bt15_scope_included_and_later_counts_are_independent(
    registry: LayoutConstraintRegistry,
) -> None:
    payload = _payload("SCOPE_01")
    payload["included"] = ["Included" for _ in range(7)]
    payload["later"] = ["Later"]
    registry.validate_slide_spec(payload)

    payload["included"] = ["Included"]
    payload["later"] = ["Later" for _ in range(5)]
    registry.validate_slide_spec(payload)


@pytest.mark.parametrize("layout_id", GROUP_A_LAYOUT_IDS)
def test_bt15_validation_leaves_source_chapter_ids_unchanged(
    layout_id: str, registry: LayoutConstraintRegistry
) -> None:
    payload = _payload(layout_id)
    before = copy.deepcopy(payload)
    registry.validate_slide_spec(payload)
    assert payload == before
    assert payload["sourceChapterIds"] == before["sourceChapterIds"]
