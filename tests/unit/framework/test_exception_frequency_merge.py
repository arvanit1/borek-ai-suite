"""LLM exception frequencies must not overwrite unsupported assembly values."""

from __future__ import annotations

from services.framework.pipeline import _merge_exception_frequencies


def test_merge_exception_frequencies_rejects_unsupported_llm_percent() -> None:
    base = [
        {"name": "New suppliers", "frequency": "named in conversation", "handling": "Hold for procurement"},
        {"name": "Rush orders", "frequency": "named in conversation", "handling": "Rush orders about 12 percent of volume"},
    ]
    draft = [
        {"name": "New suppliers", "frequency": "~12 % of total volume", "handling": "Hold for procurement"},
        {"name": "Rush orders", "frequency": "~12 % of total volume", "handling": "Rush orders about 12 percent of volume"},
    ]
    merged = _merge_exception_frequencies(base, draft)
    assert merged[0]["frequency"] == "named in conversation"
    assert merged[1]["frequency"] == "~12 % of total volume"
