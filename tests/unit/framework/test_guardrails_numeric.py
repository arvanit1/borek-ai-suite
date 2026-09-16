"""Numeric guardrail normalization — English thousands vs German decimal/grouping."""

from __future__ import annotations

from services.framework.guardrails import _numeric_token, lint_numbers


def _framework_with_kpi(text: str) -> dict:
    return {"kpis": [{"statement": text}]}


def test_numeric_token_english_thousands_comma() -> None:
    assert _numeric_token("1,250") == 1250.0


def test_numeric_token_german_decimal_comma() -> None:
    assert _numeric_token("1,7") == 1.7


def test_numeric_token_eu_dot_thousands() -> None:
    assert _numeric_token("13.500") == 13500.0


def test_lint_numbers_allows_english_thousands_in_customer_view() -> None:
    framework = _framework_with_kpi("Senior Consultant day rate is EUR 1,250 per day.")
    customer = "The day rate is EUR 1,250 per day."
    assert lint_numbers(framework, customer) == []


def test_lint_numbers_allows_equivalent_grounded_integer_without_comma() -> None:
    framework = _framework_with_kpi("Senior Consultant day rate is EUR 1,250 per day.")
    customer = "The day rate is EUR 1250 per day."
    assert lint_numbers(framework, customer) == []


def test_lint_numbers_allows_german_decimal_comma() -> None:
    framework = _framework_with_kpi("The exception rate is about 1,7 percent.")
    customer = "About 1,7 percent of invoices need manual review."
    assert lint_numbers(framework, customer) == []


def test_lint_numbers_allows_german_spaced_thousands_when_grounded() -> None:
    framework = _framework_with_kpi("Monthly spend is EUR 13 500.")
    customer = "Estimated monthly spend is EUR 13 500."
    assert lint_numbers(framework, customer) == []


def test_lint_numbers_allows_equivalent_spaced_thousands_without_space() -> None:
    framework = _framework_with_kpi("Monthly spend is EUR 13 500.")
    customer = "Estimated monthly spend is EUR 13500."
    assert lint_numbers(framework, customer) == []


def test_lint_numbers_rejects_altered_spaced_thousands() -> None:
    framework = _framework_with_kpi("Monthly spend is EUR 13 500.")
    customer = "Monthly spend is EUR 13 999."
    errors = lint_numbers(framework, customer)
    assert len(errors) == 1
    assert "13 999" in errors[0] or "999" in errors[0]


def test_lint_numbers_rejects_ungrounded_spaced_thousands() -> None:
    framework = _framework_with_kpi("Monthly spend is EUR 13 500.")
    customer = "Monthly spend is EUR 15 500."
    errors = lint_numbers(framework, customer)
    assert len(errors) == 1
    assert "15 500" in errors[0] or "500" in errors[0]


def test_lint_numbers_inspects_ungrounded_number_before_sentence_period() -> None:
    framework = _framework_with_kpi("The team processes about 200 invoices per month.")
    customer = "The team processes about 999."
    errors = lint_numbers(framework, customer)
    assert len(errors) == 1
    assert "999" in errors[0]


def test_lint_numbers_allows_grounded_spaced_thousands_before_sentence_period() -> None:
    framework = _framework_with_kpi("Monthly spend is EUR 13 500.")
    customer = "Estimated monthly spend is EUR 13 500."
    assert lint_numbers(framework, customer) == []


def test_lint_numbers_rejects_ungrounded_number() -> None:
    framework = _framework_with_kpi("The team processes about 200 invoices per month.")
    customer = "The team processes about 999 invoices per month."
    errors = lint_numbers(framework, customer)
    assert len(errors) == 1
    assert "999" in errors[0]


def test_lint_numbers_allows_eu_dot_thousands_when_grounded() -> None:
    framework = _framework_with_kpi("Monthly spend is EUR 13.500.")
    customer = "Estimated monthly spend is EUR 13.500."
    assert lint_numbers(framework, customer) == []
