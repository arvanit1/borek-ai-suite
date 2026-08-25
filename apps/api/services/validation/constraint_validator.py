"""AT-7: Generic, config-driven SlideSpec constraint validator (technical plan section 15, 18.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ConstraintValidationError(ValueError):
    """SlideSpec payload violates a layout constraint config (AT-7)."""


@dataclass(frozen=True)
class ConstraintViolation:
    path: str
    code: str
    message: str
    limit: int | None = None


_TYPE_CHECKS: dict[str, tuple[type[Any], ...]] = {
    "string": (str,),
    "array": (list,),
    "object": (dict,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
}


class LayoutConstraintRegistry:
    """Register per-layout constraint configs (BT-15 / JJ-10 / MS-12 populate this)."""

    def __init__(self) -> None:
        self._configs: dict[str, dict[str, Any]] = {}

    def register(self, layout_id: str, config: dict[str, Any]) -> None:
        if not layout_id:
            raise ValueError("layout_id must be a non-empty string")
        self._configs[layout_id] = config

    def get(self, layout_id: str) -> dict[str, Any] | None:
        return self._configs.get(layout_id)

    def validate_slide_spec(self, slide_spec: dict[str, Any]) -> None:
        layout_id = slide_spec.get("layoutId")
        if not isinstance(layout_id, str) or not layout_id:
            raise ConstraintValidationError("SlideSpec.layoutId must be a non-empty string")
        config = self._configs.get(layout_id)
        if config is None:
            raise ConstraintValidationError(
                f"No constraint config registered for layoutId {layout_id!r}"
            )
        validate_against_constraints(slide_spec, config)

    def collect_violations(self, slide_spec: dict[str, Any]) -> list[ConstraintViolation]:
        layout_id = slide_spec.get("layoutId")
        if not isinstance(layout_id, str) or not layout_id:
            return [
                ConstraintViolation(
                    path="layoutId",
                    code="missing_required",
                    message="SlideSpec.layoutId must be a non-empty string",
                )
            ]
        config = self._configs.get(layout_id)
        if config is None:
            return [
                ConstraintViolation(
                    path="layoutId",
                    code="missing_required",
                    message=f"No constraint config registered for layoutId {layout_id!r}",
                )
            ]
        return collect_constraint_violations(slide_spec, config)


def collect_constraint_violations(
    payload: dict[str, Any],
    config: dict[str, Any],
) -> list[ConstraintViolation]:
    """Return all constraint violations for AT-8 compression targeting."""
    violations: list[ConstraintViolation] = []
    _validate_payload(payload, config, violations)
    return violations


def validate_against_constraints(payload: dict[str, Any], config: dict[str, Any]) -> None:
    """Validate payload against a layout constraint config without layout-specific code."""
    violations = collect_constraint_violations(payload, config)
    if violations:
        raise ConstraintValidationError(violations[0].message)


def _validate_payload(
    payload: dict[str, Any],
    config: dict[str, Any],
    violations: list[ConstraintViolation],
) -> None:
    if not isinstance(payload, dict):
        violations.append(
            ConstraintViolation(
                path="$",
                code="invalid_payload",
                message="Constraint validation expects an object payload",
            )
        )
        return
    if not isinstance(config, dict):
        violations.append(
            ConstraintViolation(
                path="$",
                code="invalid_payload",
                message="Constraint config must be an object",
            )
        )
        return

    properties = config.get("properties")
    if properties is None:
        return
    if not isinstance(properties, dict):
        violations.append(
            ConstraintViolation(
                path="properties",
                code="invalid_payload",
                message="Constraint config.properties must be an object",
            )
        )
        return

    for field_name, field_rules in properties.items():
        if not isinstance(field_rules, dict):
            violations.append(
                ConstraintViolation(
                    path=field_name,
                    code="invalid_payload",
                    message=f"Constraint rules for {field_name!r} must be an object",
                )
            )
            continue
        _validate_field(payload, field_name, field_rules, path=field_name, violations=violations)


def _validate_field(
    container: dict[str, Any],
    field_name: str,
    rules: dict[str, Any],
    *,
    path: str,
    violations: list[ConstraintViolation],
) -> None:
    present = field_name in container
    value = container.get(field_name)

    if rules.get("required") and (not present or value is None):
        violations.append(
            ConstraintViolation(
                path=path,
                code="missing_required",
                message=f"Missing required field: {path}",
            )
        )

    if not present or value is None:
        return

    expected_type = rules.get("type")
    if expected_type is not None:
        _validate_type(value, expected_type, path=path, violations=violations)

    if expected_type == "string" and isinstance(value, str):
        _validate_string_length(value, rules, path=path, violations=violations)

    if expected_type == "array" and isinstance(value, list):
        _validate_array_count(value, rules, path=path, violations=violations)
        item_rules = rules.get("items")
        if isinstance(item_rules, dict):
            for index, item in enumerate(value):
                item_path = f"{path}[{index}]"
                item_type = item_rules.get("type")
                if item_type is not None:
                    _validate_type(item, item_type, path=item_path, violations=violations)
                if item_type == "string" and isinstance(item, str):
                    _validate_string_length(item, item_rules, path=item_path, violations=violations)
                item_properties = item_rules.get("properties")
                if isinstance(item_properties, dict) and isinstance(item, dict):
                    for nested_name, nested_rules in item_properties.items():
                        if isinstance(nested_rules, dict):
                            _validate_field(
                                item,
                                nested_name,
                                nested_rules,
                                path=f"{item_path}.{nested_name}",
                                violations=violations,
                            )

    if expected_type == "object" and isinstance(value, dict):
        nested_properties = rules.get("properties")
        if isinstance(nested_properties, dict):
            for nested_name, nested_rules in nested_properties.items():
                if isinstance(nested_rules, dict):
                    _validate_field(
                        value,
                        nested_name,
                        nested_rules,
                        path=f"{path}.{nested_name}",
                        violations=violations,
                    )


def _validate_type(
    value: Any,
    expected_type: str,
    *,
    path: str,
    violations: list[ConstraintViolation],
) -> None:
    if expected_type not in _TYPE_CHECKS:
        violations.append(
            ConstraintViolation(
                path=path,
                code="unsupported_type",
                message=f"Unsupported constraint type {expected_type!r} at {path}",
            )
        )
        return
    allowed = _TYPE_CHECKS[expected_type]
    if expected_type == "integer" and isinstance(value, bool):
        violations.append(
            ConstraintViolation(
                path=path,
                code="type_mismatch",
                message=f"Expected integer at {path}, got boolean",
            )
        )
        return
    if not isinstance(value, allowed):
        violations.append(
            ConstraintViolation(
                path=path,
                code="type_mismatch",
                message=f"Expected {expected_type} at {path}, got {type(value).__name__}",
            )
        )


def _validate_string_length(
    value: str,
    rules: dict[str, Any],
    *,
    path: str,
    violations: list[ConstraintViolation],
) -> None:
    min_length = rules.get("min_length")
    max_length = rules.get("max_length")
    if min_length is not None and len(value) < min_length:
        violations.append(
            ConstraintViolation(
                path=path,
                code="min_length",
                message=f"Field {path} length {len(value)} is below minimum {min_length}",
                limit=min_length,
            )
        )
    if max_length is not None and len(value) > max_length:
        violations.append(
            ConstraintViolation(
                path=path,
                code="max_length",
                message=f"Field {path} length {len(value)} exceeds maximum {max_length}",
                limit=max_length,
            )
        )


def _validate_array_count(
    value: list[Any],
    rules: dict[str, Any],
    *,
    path: str,
    violations: list[ConstraintViolation],
) -> None:
    min_items = rules.get("min_items")
    max_items = rules.get("max_items")
    if min_items is not None and len(value) < min_items:
        violations.append(
            ConstraintViolation(
                path=path,
                code="min_items",
                message=f"Field {path} item count {len(value)} is below minimum {min_items}",
                limit=min_items,
            )
        )
    if max_items is not None and len(value) > max_items:
        violations.append(
            ConstraintViolation(
                path=path,
                code="max_items",
                message=f"Field {path} item count {len(value)} exceeds maximum {max_items}",
                limit=max_items,
            )
        )
