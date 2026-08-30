"""Official OpenAI Responses API transport for provider-agnostic LLM calls."""

from __future__ import annotations

import copy
import json
from typing import Any

from llm.client import LlmUsageResult
from services.observability.llm_logger import LlmStage


class OpenAIProviderError(RuntimeError):
    """Base error for OpenAI transport and response failures."""


class OpenAIProviderConfigurationError(OpenAIProviderError):
    """The live OpenAI provider is not configured correctly."""


class OpenAIPlanningResponseError(OpenAIProviderError):
    """OpenAI did not return a usable structured PresentationPlan."""


class OpenAIResponsesExecutor:
    """Execute one schema-constrained BT-1 request through OpenAI Responses."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip():
            raise OpenAIProviderConfigurationError(
                "OPENAI_API_KEY is required for live OpenAI execution"
            )
        if not model.strip():
            raise OpenAIProviderConfigurationError(
                "OPENAI_PRESENTATION_MODEL must be a non-empty model ID"
            )
        self._model = model
        self._client = client if client is not None else _create_openai_client(api_key)

    def __call__(
        self,
        stage: LlmStage,
        operation: str,
        prompt_version: str,
        retry_count: int,
        *,
        request: dict[str, Any] | None = None,
    ) -> LlmUsageResult:
        _ = (prompt_version, retry_count)
        if stage != LlmStage.PLANNING or operation != "presentation_planner":
            raise OpenAIProviderError(
                "OpenAIResponsesExecutor currently supports BT-1 planning only"
            )
        if not isinstance(request, dict):
            raise OpenAIProviderError("BT-1 planning input must be an object")

        instructions = request.get("instructions")
        target_schema = request.get("targetSchema")
        if not isinstance(instructions, str) or not instructions.strip():
            raise OpenAIProviderError("BT-1 planning instructions are required")
        if not isinstance(target_schema, dict):
            raise OpenAIProviderError("BT-1 canonical targetSchema is required")

        model_input = copy.deepcopy(request)
        model_input.pop("instructions", None)
        response = self._client.responses.create(
            model=self._model,
            instructions=instructions,
            input=json.dumps(model_input, ensure_ascii=False),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "presentation_plan",
                    "schema": copy.deepcopy(target_schema),
                    # The canonical schema intentionally permits root extensions.
                    # BT-1 performs the authoritative validation after this response.
                    "strict": False,
                }
            },
            store=False,
        )
        return _to_usage_result(response)


def _create_openai_client(api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - production dependency guard
        raise OpenAIProviderConfigurationError(
            "The official openai package is required for live execution"
        ) from exc
    return OpenAI(api_key=api_key)


def _to_usage_result(response: Any) -> LlmUsageResult:
    status = _field(response, "status")
    if status != "completed":
        detail = _field(response, "error") or _field(response, "incomplete_details")
        raise OpenAIPlanningResponseError(
            f"OpenAI planning response did not complete: {status!r} ({detail!r})"
        )
    if _contains_refusal(_field(response, "output")):
        raise OpenAIPlanningResponseError(
            "OpenAI refused the presentation planning request"
        )

    output_text = _field(response, "output_text")
    if not isinstance(output_text, str) or not output_text.strip():
        raise OpenAIPlanningResponseError(
            "OpenAI planning response contained no structured output"
        )
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise OpenAIPlanningResponseError(
            "OpenAI planning response was not valid structured JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise OpenAIPlanningResponseError(
            "OpenAI planning response must be a JSON object"
        )

    usage = _field(response, "usage")
    return LlmUsageResult(
        payload=payload,
        input_tokens=_token_count(usage, "input_tokens"),
        output_tokens=_token_count(usage, "output_tokens"),
    )


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _token_count(usage: Any, name: str) -> int:
    value = _field(usage, name)
    return value if isinstance(value, int) and value >= 0 else 0


def _contains_refusal(output: Any) -> bool:
    if not isinstance(output, list):
        return False
    for item in output:
        content = _field(item, "content")
        if not isinstance(content, list):
            continue
        if any(_field(part, "type") == "refusal" for part in content):
            return True
    return False
