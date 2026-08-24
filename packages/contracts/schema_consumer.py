"""AT-6: Forward-compatible contract consumers (schema_version + additive fields)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from generated.python.contracts.framework_object import FrameworkObject
    from generated.python.contracts.presentation_plan import PresentationPlan
    from generated.python.contracts.slide_spec_base import SlideSpecBase

CONTRACTS_DIR = Path(__file__).resolve().parent

ModelT = TypeVar("ModelT", bound=BaseModel)


class SchemaVersionMismatchError(ValueError):
    """Payload is incompatible with the consumer's supported contract version (AT-6)."""


def _load_schema(relative_path: str) -> dict[str, Any]:
    schema_path = CONTRACTS_DIR / relative_path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _supported_schema_version(schema: dict[str, Any]) -> str:
    version_schema = schema["properties"]["schema_version"]
    const = version_schema.get("const")
    if not isinstance(const, str):
        raise RuntimeError("Contract schema must define schema_version const")
    return const


def _required_fields(schema: dict[str, Any]) -> frozenset[str]:
    required = schema.get("required")
    if not isinstance(required, list):
        raise RuntimeError("Contract schema must define required fields")
    return frozenset(required)


def _known_property_keys(schema: dict[str, Any]) -> frozenset[str]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise RuntimeError("Contract schema must define properties")
    return frozenset(properties.keys())


def _ensure_mapping(raw: Any, contract_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SchemaVersionMismatchError(
            f"{contract_name} schema_version mismatch: expected object payload, got {type(raw).__name__}"
        )
    return raw


def _validate_version_and_required(
    payload: dict[str, Any],
    *,
    contract_name: str,
    schema: dict[str, Any],
) -> None:
    supported = _supported_schema_version(schema)

    missing = sorted(_required_fields(schema) - payload.keys())
    if missing:
        joined = ", ".join(missing)
        raise SchemaVersionMismatchError(
            f"{contract_name} schema_version {supported} mismatch: missing required field(s): {joined}"
        )

    version = payload.get("schema_version")
    if version != supported:
        raise SchemaVersionMismatchError(
            f"{contract_name} schema_version mismatch: unsupported version {version!r} "
            f"(supported: {supported!r})"
        )


def _strip_unrecognized_additive_fields(
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    known = _known_property_keys(schema)
    return {key: value for key, value in payload.items() if key in known}


def _consume_contract(
    raw: Any,
    *,
    contract_name: str,
    schema_path: str,
    model_type: type[ModelT],
    strip_additive: bool,
) -> ModelT:
    schema = _load_schema(schema_path)
    payload = _ensure_mapping(raw, contract_name)
    _validate_version_and_required(payload, contract_name=contract_name, schema=schema)
    normalized = _strip_unrecognized_additive_fields(payload, schema) if strip_additive else payload
    return model_type.model_validate(normalized)


def consume_framework_object(raw: Any) -> FrameworkObject:
    """Parse FrameworkObject, ignoring unrecognized additive root fields (AT-6)."""
    from generated.python.contracts.framework_object import FrameworkObject as FrameworkObjectModel

    return _consume_contract(
        raw,
        contract_name="FrameworkObject",
        schema_path="framework_object.schema.json",
        model_type=FrameworkObjectModel,
        strip_additive=True,
    )


def consume_presentation_plan(raw: Any) -> PresentationPlan:
    """Parse PresentationPlan, ignoring unrecognized additive root fields (AT-6)."""
    from generated.python.contracts.presentation_plan import PresentationPlan as PresentationPlanModel

    return _consume_contract(
        raw,
        contract_name="PresentationPlan",
        schema_path="presentation_plan.schema.json",
        model_type=PresentationPlanModel,
        strip_additive=True,
    )


def consume_slide_spec_base(raw: Any) -> SlideSpecBase:
    """Parse SlideSpec base fields; preserve layout-specific extensions (AT-3, AT-6)."""
    from generated.python.contracts.slide_spec_base import SlideSpecBase as SlideSpecBaseModel

    return _consume_contract(
        raw,
        contract_name="SlideSpecBase",
        schema_path="slide_spec/base.schema.json",
        model_type=SlideSpecBaseModel,
        strip_additive=False,
    )
