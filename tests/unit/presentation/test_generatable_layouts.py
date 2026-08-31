"""Approved-plan filtering: AT-10 may only compare generatable slides."""

from __future__ import annotations

import copy

import pytest

from services.presentation.generatable_layouts import (
    as_approved_generatable_plan,
    filter_generatable_planned_slides,
)


def _slide(order: int, layout_id: str) -> dict[str, object]:
    return {
        "order": order,
        "purpose": layout_id.lower(),
        "layoutId": layout_id,
        "frameworkReferences": ["chapter_1"],
    }


def test_approved_plan_strips_unimplemented_layouts_and_renumbers() -> None:
    dirty = {
        "schema_version": "1.0",
        "title": "Invoice automation",
        "slides": [
            _slide(1, "COVER_01"),
            _slide(2, "EXECUTIVE_SUMMARY_01"),
            _slide(3, "CONTEXT_01"),
        ],
    }
    original = copy.deepcopy(dirty)

    approved = as_approved_generatable_plan(dirty)

    assert dirty == original
    assert [slide["layoutId"] for slide in approved["slides"]] == ["COVER_01", "CONTEXT_01"]
    assert [slide["order"] for slide in approved["slides"]] == [1, 2]
    assert approved["title"] == "Invoice automation"
    kept, skipped = filter_generatable_planned_slides(approved)
    assert skipped == []
    assert len(kept) == 2


def test_approved_plan_rejects_only_unimplemented_layouts() -> None:
    with pytest.raises(ValueError, match="at least one generatable slide"):
        as_approved_generatable_plan(
            {"slides": [_slide(1, "EXECUTIVE_SUMMARY_01")]}
        )
