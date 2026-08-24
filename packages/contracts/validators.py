"""Business-rule validators beyond JSON Schema expressiveness."""

from __future__ import annotations

from typing import Any


class ContractValidationError(ValueError):
    pass


def validate_presentation_plan_business_rules(plan: dict[str, Any]) -> None:
    """AT-2 supplemental rules: unique, contiguous slide order starting at 1."""
    slides = plan.get("slides", [])
    if not slides:
        raise ContractValidationError("PresentationPlan must contain at least one slide")

    orders = [slide["order"] for slide in slides]
    if len(orders) != len(set(orders)):
        raise ContractValidationError("PlannedSlide.order values must be unique")

    expected = list(range(1, len(slides) + 1))
    if sorted(orders) != expected:
        raise ContractValidationError(
            f"PlannedSlide.order must be contiguous 1..{len(slides)}; got {sorted(orders)}"
        )


def layout_ids_from_registry(registry: dict[str, Any]) -> set[str]:
    layouts = registry.get("layouts")
    if not isinstance(layouts, dict):
        raise ContractValidationError("layout_registry.json must contain a layouts object")
    return set(layouts.keys())


def layout_ids_from_presentation_schema(schema: dict[str, Any]) -> set[str]:
    layout_id = schema["$defs"]["LayoutId"]
    enum_values = layout_id.get("enum")
    if not enum_values:
        raise ContractValidationError("PresentationPlan schema LayoutId enum is missing")
    return set(enum_values)


def layout_ids_from_slide_spec_base_schema(schema: dict[str, Any]) -> set[str]:
    layout_id = schema["$defs"]["LayoutId"]
    enum_values = layout_id.get("enum")
    if not enum_values:
        raise ContractValidationError("SlideSpec base schema LayoutId enum is missing")
    return set(enum_values)


def chapter_specs_from_registry(registry: dict[str, Any]) -> list[tuple[str, str]]:
    chapters = registry.get("chapters")
    if not isinstance(chapters, list) or len(chapters) != 14:
        raise ContractValidationError("chapter_registry.json must list exactly 14 chapters")
    specs: list[tuple[str, str]] = []
    for chapter in chapters:
        specs.append((chapter["chapter_id"], chapter["title"]))
    return specs


def chapter_specs_from_framework_schema(schema: dict[str, Any]) -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    for index in range(14):
        ref = schema["$defs"][f"ChapterAtIndex{index}"]
        chapter_id = None
        title = None
        for part in ref["allOf"]:
            props = part.get("properties", {})
            if "chapter_id" in props and "const" in props["chapter_id"]:
                chapter_id = props["chapter_id"]["const"]
            if "title" in props and "const" in props["title"]:
                title = props["title"]["const"]
        if chapter_id is None or title is None:
            raise ContractValidationError(f"ChapterAtIndex{index} missing const id/title")
        specs.append((chapter_id, title))
    return specs
