"""Bundle layout SlideSpec schemas so OpenAI receives only in-document $refs."""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BASE_SCHEMA_PATH = (
    _REPO_ROOT / "packages" / "contracts" / "slide_spec" / "base.schema.json"
)
_CONSTRAINT_DIR = _REPO_ROOT / "packages" / "contracts" / "constraints"


class JsonSchemaBundleError(ValueError):
    """A layout schema could not be rewritten for OpenAI structured output."""


_OPENAI_ROOT_FORBIDDEN = frozenset({"oneOf", "anyOf", "allOf", "enum", "const", "not"})


def layout_constraint_config(layout_id: str) -> dict[str, Any] | None:
    """Return the registered BT-15 / JJ-10 / MS-12 limit config for a layout."""
    if not layout_id:
        return None
    config = _constraint_layouts().get(layout_id)
    return copy.deepcopy(config) if isinstance(config, dict) else None


def prepare_openai_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a schema OpenAI structured output can accept.

    Canonical SlideSpec contracts stay unchanged. Only the request-facing copy is
    rewritten: external $refs are inlined, ``allOf`` is flattened, and registered
    BT-15 / JJ-10 / MS-12 item and length limits are copied onto the schema so
    OpenAI cannot emit a structurally illegal SlideSpec. AT-8 still compresses
    overflowing strings; item-count violations stay fail-closed.
    """
    if not isinstance(schema, dict):
        raise JsonSchemaBundleError("targetSchema must be an object")
    needs_rewrite = _has_external_ref(schema) or _has_keyword(schema, "allOf")
    if not needs_rewrite:
        return copy.deepcopy(schema)
    prepared = copy.deepcopy(schema)
    if _has_external_ref(prepared):
        prepared = _bundle_with_base(prepared)
    prepared = _flatten_allof(prepared)
    prepared = _apply_registered_limits(prepared)
    return _require_openai_root(prepared)


def _bundle_with_base(schema: dict[str, Any]) -> dict[str, Any]:
    bundled = copy.deepcopy(schema)
    base = _load_base_schema()
    base_defs = copy.deepcopy(base.get("$defs") or {})
    base_defs["SlideSpecBase"] = {
        key: copy.deepcopy(base[key])
        for key in ("type", "additionalProperties", "required", "properties")
        if key in base
    }
    layout_defs = copy.deepcopy(bundled.get("$defs") or {})
    bundled["$defs"] = {**base_defs, **layout_defs}
    if "SlideSpecBase" not in layout_defs:
        bundled["$defs"]["SlideSpecBase"] = base_defs["SlideSpecBase"]
    rewritten = _rewrite_refs(bundled, base)
    if _has_external_ref(rewritten):
        raise JsonSchemaBundleError("Layout schema still contains an external $ref")
    return rewritten


def _rewrite_refs(node: Any, base: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_rewrite_refs(item, base) for item in node]
    if not isinstance(node, dict):
        return copy.deepcopy(node)
    ref = node.get("$ref")
    if isinstance(ref, str) and not ref.startswith("#"):
        replacement = _resolve_external_ref(ref, base)
        extras = {key: value for key, value in node.items() if key != "$ref"}
        if extras:
            if not isinstance(replacement, dict):
                raise JsonSchemaBundleError(f"Cannot merge extras onto $ref {ref}")
            replacement = {**replacement, **extras}
        return _rewrite_refs(replacement, base)
    return {key: _rewrite_refs(value, base) for key, value in node.items()}


def _resolve_external_ref(ref: str, base: dict[str, Any]) -> Any:
    if "base.schema.json#" not in ref and "slide_spec/base/" not in ref:
        raise JsonSchemaBundleError(f"Unsupported schema $ref: {ref}")
    fragment = ref.split("#", 1)[1] if "#" in ref else ""
    if fragment.startswith("/$defs/"):
        return {"$ref": f"#{fragment}"}
    return copy.deepcopy(_json_pointer(base, fragment))


def _json_pointer(document: dict[str, Any], fragment: str) -> Any:
    if fragment == "":
        return document
    if not fragment.startswith("/"):
        raise JsonSchemaBundleError(f"Unsupported schema pointer: {fragment}")
    current: Any = document
    for raw in fragment.lstrip("/").split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or key not in current:
            raise JsonSchemaBundleError(f"Unresolved schema pointer {fragment}")
        current = current[key]
    return current


def _flatten_allof(schema: dict[str, Any]) -> dict[str, Any]:
    working = copy.deepcopy(schema)
    defs = working.get("$defs")
    if isinstance(defs, dict):
        working["$defs"] = {
            name: _flatten_node(value, working)
            for name, value in defs.items()
        }
    flattened = _flatten_node(working, working)
    if not isinstance(flattened, dict):
        raise JsonSchemaBundleError("Flattened schema must be an object")
    return flattened


def _flatten_node(node: Any, root: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_flatten_node(item, root) for item in node]
    if not isinstance(node, dict):
        return copy.deepcopy(node)
    current = {
        key: _flatten_node(value, root)
        for key, value in node.items()
        if key != "allOf"
    }
    allof = node.get("allOf")
    if not isinstance(allof, list):
        return current
    merged: dict[str, Any] = {}
    for part in allof:
        resolved = _resolve_local_ref(part, root)
        flattened_part = _flatten_node(resolved, root)
        if not isinstance(flattened_part, dict):
            raise JsonSchemaBundleError("allOf parts must be objects")
        merged = _merge_object_schemas(merged, flattened_part)
    return _merge_object_schemas(merged, current)


def _resolve_local_ref(node: Any, root: dict[str, Any]) -> Any:
    if not isinstance(node, dict):
        return copy.deepcopy(node)
    ref = node.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#"):
        return copy.deepcopy(node)
    resolved = copy.deepcopy(_json_pointer(root, ref[1:]))
    extras = {key: value for key, value in node.items() if key != "$ref"}
    if extras:
        if not isinstance(resolved, dict):
            raise JsonSchemaBundleError(f"Cannot merge extras onto $ref {ref}")
        return {**resolved, **extras}
    return resolved


def _merge_object_schemas(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    if not left:
        return copy.deepcopy(right)
    merged = copy.deepcopy(left)
    for key, value in right.items():
        if key == "properties" and isinstance(value, dict):
            properties = dict(merged.get("properties") or {})
            properties.update(copy.deepcopy(value))
            merged["properties"] = properties
        elif key == "required" and isinstance(value, list):
            required = list(merged.get("required") or [])
            for item in value:
                if item not in required:
                    required.append(item)
            merged["required"] = required
        elif key == "$defs" and isinstance(value, dict):
            defs = dict(merged.get("$defs") or {})
            defs.update(copy.deepcopy(value))
            merged["$defs"] = defs
        elif key == "additionalProperties":
            if value is False or merged.get("additionalProperties") is False:
                merged["additionalProperties"] = False
            else:
                merged["additionalProperties"] = copy.deepcopy(value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _apply_registered_limits(schema: dict[str, Any]) -> dict[str, Any]:
    layout_id = _layout_id_from_schema(schema)
    if layout_id is None:
        return schema
    limits = _constraint_layouts().get(layout_id)
    if not isinstance(limits, dict):
        return schema
    properties = schema.get("properties")
    constraint_properties = limits.get("properties")
    if not isinstance(properties, dict) or not isinstance(constraint_properties, dict):
        return schema
    _merge_constraint_limits(properties, constraint_properties, schema)
    return schema


def _layout_id_from_schema(schema: dict[str, Any]) -> str | None:
    layout = (schema.get("properties") or {}).get("layoutId")
    if isinstance(layout, dict) and isinstance(layout.get("const"), str):
        return layout["const"]
    return None


def _merge_constraint_limits(
    schema_properties: dict[str, Any],
    constraint_properties: dict[str, Any],
    root: dict[str, Any],
) -> None:
    for name, rules in constraint_properties.items():
        if not isinstance(rules, dict):
            continue
        target = _deref_schema_node(schema_properties.get(name) or {}, root)
        if not isinstance(target, dict):
            target = {}
        schema_properties[name] = target
        if isinstance(rules.get("max_length"), int):
            target["maxLength"] = rules["max_length"]
        if isinstance(rules.get("min_items"), int):
            target["minItems"] = rules["min_items"]
        if isinstance(rules.get("max_items"), int):
            target["maxItems"] = rules["max_items"]
        item_rules = rules.get("items")
        if isinstance(item_rules, dict):
            items = _deref_schema_node(target.get("items") or {}, root)
            if not isinstance(items, dict):
                items = {}
            target["items"] = items
            if isinstance(item_rules.get("max_length"), int):
                items["maxLength"] = item_rules["max_length"]
            nested_item_properties = item_rules.get("properties")
            if isinstance(nested_item_properties, dict):
                item_properties = items.setdefault("properties", {})
                if isinstance(item_properties, dict):
                    _merge_constraint_limits(item_properties, nested_item_properties, root)
        nested_properties = rules.get("properties")
        if isinstance(nested_properties, dict):
            child_properties = target.setdefault("properties", {})
            if isinstance(child_properties, dict):
                _merge_constraint_limits(child_properties, nested_properties, root)


def _deref_schema_node(node: Any, root: dict[str, Any]) -> Any:
    if (
        isinstance(node, dict)
        and isinstance(node.get("$ref"), str)
        and node["$ref"].startswith("#")
    ):
        return copy.deepcopy(_json_pointer(root, node["$ref"][1:]))
    return node


@lru_cache(maxsize=1)
def _constraint_layouts() -> dict[str, dict[str, Any]]:
    import json

    layouts: dict[str, dict[str, Any]] = {}
    for path in sorted(_CONSTRAINT_DIR.glob("*.yaml")):
        document = json.loads(path.read_text(encoding="utf-8"))
        raw = document.get("layouts")
        if not isinstance(raw, dict):
            continue
        for layout_id, config in raw.items():
            if isinstance(layout_id, str) and isinstance(config, dict):
                layouts[layout_id] = config
    return layouts


def _require_openai_root(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type") != "object":
        raise JsonSchemaBundleError("OpenAI schema must have type 'object'")
    forbidden = sorted(key for key in _OPENAI_ROOT_FORBIDDEN if key in schema)
    if forbidden:
        raise JsonSchemaBundleError(
            "OpenAI schema must not have "
            + "/".join(repr(key) for key in forbidden)
            + " at the top level"
        )
    return schema


def _has_keyword(node: Any, keyword: str) -> bool:
    if isinstance(node, list):
        return any(_has_keyword(item, keyword) for item in node)
    if not isinstance(node, dict):
        return False
    if keyword in node:
        return True
    return any(_has_keyword(value, keyword) for value in node.values())


def _has_external_ref(node: Any) -> bool:
    if isinstance(node, list):
        return any(_has_external_ref(item) for item in node)
    if not isinstance(node, dict):
        return False
    ref = node.get("$ref")
    if isinstance(ref, str) and not ref.startswith("#"):
        return True
    return any(_has_external_ref(value) for value in node.values())


@lru_cache(maxsize=1)
def _load_base_schema() -> dict[str, Any]:
    if not _BASE_SCHEMA_PATH.is_file():
        raise JsonSchemaBundleError(
            f"Missing SlideSpec base schema at {_BASE_SCHEMA_PATH}"
        )
    import json

    loaded = json.loads(_BASE_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise JsonSchemaBundleError("SlideSpec base schema must be an object")
    return loaded
