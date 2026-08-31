"""ES-32 — Claude localization for customer reports."""

from __future__ import annotations

from typing import Any, Callable

from llm.claude.client import (
    CLAUDE_STRUCTURED_MAX_TOKENS,
    ClaudeClientError,
    structured_complete,
    sonnet_model,
)
from services.observability.llm_logger import STAGE_LOCALIZE, run_logged_llm_call

LocalizeFn = Callable[[str, str, dict[str, Any]], dict[str, Any]]


def make_localize_fn(
    *,
    opportunity_id: str | None = None,
    framework_id: str | None = None,
) -> LocalizeFn:
    def _localize(system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        usage_holder: list[Any] = []

        def invoke() -> dict[str, Any]:
            try:
                return structured_complete(
                    system,
                    user,
                    schema,
                    tool_name="submit_localized_report",
                    tool_description="Submit the localized customer report JSON.",
                    max_tokens=CLAUDE_STRUCTURED_MAX_TOKENS,
                    temperature=0,
                    usage_out=usage_holder,
                )
            except ClaudeClientError as exc:
                raise ValueError(exc.user_message) from exc

        localized = run_logged_llm_call(
            stage=STAGE_LOCALIZE,
            prompt_version="framework-localize:v1",
            model=sonnet_model(),
            attempt=1,
            opportunity_id=opportunity_id,
            framework_id=framework_id,
            invoke=invoke,
            usage_out=usage_holder,
        )
        if not isinstance(localized, dict):
            raise ValueError("German localization did not return a JSON object.")
        return localized

    return _localize
