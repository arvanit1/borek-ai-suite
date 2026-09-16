"""Stage 1 FE-02: canonical validation at Framework persistence boundaries."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from packages.contracts.schema_consumer import (
    FrameworkObjectValidationError,
    validate_framework_object,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "packages" / "contracts" / "fixtures" / "framework_object.minimal.json"


def _framework() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_canonical_framework_validation_preserves_additive_root_fields() -> None:
    framework = _framework()
    framework["future_field"] = {"preserved": True}
    framework["customer_view"] = {"display": "additive projection"}
    before = copy.deepcopy(framework)

    validate_framework_object(framework)

    assert framework == before


@pytest.mark.parametrize(
    ("mutate", "path"),
    [
        (lambda value: value.pop("title"), "/"),
        (lambda value: value.update(status="invalid"), "/status"),
        (lambda value: value.update(chapters=value["chapters"][:-1]), "/chapters"),
        (lambda value: value["chapters"][3].update(chapter_id="4"), "/chapters/3/chapter_id"),
        (lambda value: value["chapters"][3].pop("source_refs"), "/chapters/3"),
    ],
)
def test_canonical_framework_validation_reports_contract_path(mutate, path: str) -> None:
    framework = _framework()
    mutate(framework)

    with pytest.raises(FrameworkObjectValidationError) as caught:
        validate_framework_object(framework)

    assert any(error["path"] == path for error in caught.value.errors)
    assert caught.value.code == "FRAMEWORK_VALIDATION_FAILED"
    assert caught.value.retryable is False
