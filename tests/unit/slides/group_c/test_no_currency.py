"""MS-14: SUCCESS_METRICS_01 rejects currency and ROI-style copy in code."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from services.slides.business_rules import (
    ProhibitedCurrencyContentError,
    reject_success_metrics_currency,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURE_PATH = (
    ROOT
    / "packages"
    / "contracts"
    / "fixtures"
    / "slide_spec"
    / "success_metrics_01.minimal.json"
)
ARCHITECTURE_FIXTURE_PATH = (
    ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "architecture_01.minimal.json"
)


def _metrics() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_ms14_invoice_metrics_fixture_passes() -> None:
    payload = _metrics()
    before = copy.deepcopy(payload)
    reject_success_metrics_currency(payload)
    assert payload == before


def test_ms14_non_monetary_percent_metric_passes() -> None:
    payload = _metrics()
    payload["criteria"][0]["description"] = "Invoices auto-matched without a manual check"
    payload["title"] = "How we measure operational success"
    reject_success_metrics_currency(payload)


@pytest.mark.parametrize(
    ("field_path", "prohibited"),
    [
        ("title", "Save €100k in year one"),
        ("subtitle", "Target USD 50,000"),
        ("criteria[0].title", "ROI 25%"),
        ("criteria[0].description", "Payback in 6 months"),
        ("criteria[1].description", "Budget of $10,000"),
        ("criteria[0].description", "EUR 100 per invoice"),
        ("criteria[0].description", "Return on investment of 3x"),
        ("criteria[0].description", "Annual cost savings of 20%"),
    ],
)
def test_ms14_rejects_currency_and_roi_copy(field_path: str, prohibited: str) -> None:
    payload = _metrics()
    if field_path == "title":
        payload["title"] = prohibited
        expected_path = "$.title"
    elif field_path == "subtitle":
        payload["subtitle"] = prohibited
        expected_path = "$.subtitle"
    elif field_path.startswith("criteria["):
        index = int(field_path[len("criteria[") :].split("]", 1)[0])
        nested = field_path.rsplit(".", 1)[1]
        payload["criteria"][index][nested] = prohibited
        expected_path = f"$.criteria[{index}].{nested}"
    else:  # pragma: no cover
        raise AssertionError(field_path)

    with pytest.raises(ProhibitedCurrencyContentError, match=re.escape(expected_path)):
        reject_success_metrics_currency(payload)


def test_ms14_does_not_strip_or_rewrite_on_failure() -> None:
    payload = _metrics()
    payload["criteria"][0]["description"] = "Save €40,000 a year"
    before = copy.deepcopy(payload)
    with pytest.raises(ProhibitedCurrencyContentError):
        reject_success_metrics_currency(payload)
    assert payload == before


def test_ms14_ignores_other_layouts() -> None:
    payload = json.loads(ARCHITECTURE_FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["title"] = "Save €100k"
    reject_success_metrics_currency(payload)


def test_ms14_does_not_live_in_constraint_validator() -> None:
    source = (
        ROOT / "apps" / "api" / "services" / "validation" / "constraint_validator.py"
    ).read_text(encoding="utf-8")
    assert "SUCCESS_METRICS_01" not in source
    assert "€" not in source
