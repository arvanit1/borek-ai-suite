"""Official OpenAI Responses API transport for provider-agnostic LLM calls."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from llm.client import LlmUsageResult
from llm.json_schema_bundle import JsonSchemaBundleError, prepare_openai_json_schema
from services.observability.llm_logger import LlmStage


class OpenAIProviderError(RuntimeError):
    """Base error for OpenAI transport and response failures."""

    def __init__(
        self,
        message: str = "",
        *,
        code: str = "",
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        if code:
            self.code = code
        if retryable is not None:
            self.retryable = retryable


class OpenAIProviderConfigurationError(OpenAIProviderError):
    """The live OpenAI provider is not configured correctly."""


class OpenAIStructuredResponseError(OpenAIProviderError):
    """OpenAI did not return usable structured JSON."""


class OpenAIPlanningResponseError(OpenAIStructuredResponseError):
    """OpenAI did not return a usable structured PresentationPlan."""


class OpenAISlideGenerationResponseError(OpenAIStructuredResponseError):
    """OpenAI did not return a usable structured SlideSpec."""


class OpenAICompressionResponseError(OpenAIStructuredResponseError):
    """OpenAI did not return usable compressed field values."""


@dataclass(frozen=True)
class _OperationSpec:
    schema_name: str
    error_cls: type[OpenAIStructuredResponseError]
    label: str
    kind: str


class OpenAIResponsesExecutor:
    """Execute schema-constrained Stage B requests through OpenAI Responses."""

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
        spec = _operation_spec(stage, operation)
        if spec is None:
            raise OpenAIProviderError(
                f"OpenAIResponsesExecutor does not support {stage.value}/{operation}"
            )
        if not isinstance(request, dict):
            raise OpenAIProviderError(f"{spec.label} input must be an object")

        from services.security.egress_policy import EgressBlockedError, enforce_external_egress

        try:
            request = enforce_external_egress(
                copy.deepcopy(request),
                provider="openai",
                stage=spec.kind,
            )
        except EgressBlockedError as exc:
            raise OpenAIProviderError(str(exc), code=exc.code, retryable=False) from exc
        if not isinstance(request, dict):
            raise OpenAIProviderError(f"{spec.label} input must be an object")

        instructions = request.get("instructions")
        target_schema = request.get("targetSchema")
        if not isinstance(instructions, str) or not instructions.strip():
            raise OpenAIProviderError(f"{spec.label} instructions are required")
        if not isinstance(target_schema, dict):
            raise OpenAIProviderError(f"{spec.label} canonical targetSchema is required")
        if spec.kind == "slide" and not isinstance(request.get("chapters"), (list, tuple)):
            raise OpenAIProviderError("Slide generation chapters must be an array")
        if spec.kind == "compression" and not isinstance(
            request.get("offendingValues"), dict
        ):
            raise OpenAIProviderError("Compression offendingValues must be an object")

        try:
            schema_for_api = prepare_openai_json_schema(target_schema)
        except JsonSchemaBundleError as exc:
            raise OpenAIProviderError(f"{spec.label} targetSchema is not usable: {exc}") from exc

        model_input = copy.deepcopy(request)
        model_input.pop("instructions", None)
        response = self._client.responses.create(
            model=self._model,
            instructions=instructions,
            input=json.dumps(model_input, ensure_ascii=False),
            text={
                "format": {
                    "type": "json_schema",
                    "name": spec.schema_name,
                    "schema": schema_for_api,
                    "strict": False,
                }
            },
            store=False,
        )
        return _to_usage_result(response, error_cls=spec.error_cls, label=spec.label)


def _operation_spec(stage: LlmStage, operation: str) -> _OperationSpec | None:
    if stage == LlmStage.PLANNING and operation == "presentation_planner":
        return _OperationSpec(
            schema_name="presentation_plan",
            error_cls=OpenAIPlanningResponseError,
            label="BT-1 planning",
            kind="planning",
        )
    if stage == LlmStage.SLIDE_GENERATION:
        return _OperationSpec(
            schema_name=_schema_format_name(operation),
            error_cls=OpenAISlideGenerationResponseError,
            label="slide generation",
            kind="slide",
        )
    if stage == LlmStage.COMPRESSION and operation == "compression":
        return _OperationSpec(
            schema_name="compressed_fields",
            error_cls=OpenAICompressionResponseError,
            label="compression",
            kind="compression",
        )
    return None


def _schema_format_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in value)
    if not cleaned:
        raise OpenAIProviderError("Structured output schema name is empty")
    return cleaned[:64]


def _create_openai_client(api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - production dependency guard
        raise OpenAIProviderConfigurationError(
            "The official openai package is required for live execution"
        ) from exc
    return OpenAI(api_key=api_key)


def _to_usage_result(
    response: Any,
    *,
    error_cls: type[OpenAIStructuredResponseError] = OpenAIPlanningResponseError,
    label: str = "planning",
) -> LlmUsageResult:
    status = _field(response, "status")
    if status != "completed":
        detail = _field(response, "error") or _field(response, "incomplete_details")
        raise error_cls(
            f"OpenAI {label} response did not complete: {status!r} ({detail!r})"
        )
    if _contains_refusal(_field(response, "output")):
        raise error_cls(f"OpenAI refused the {label} request")

    output_text = _field(response, "output_text")
    if not isinstance(output_text, str) or not output_text.strip():
        raise error_cls(f"OpenAI {label} response contained no structured output")
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise error_cls(f"OpenAI {label} response was not valid structured JSON") from exc
    if not isinstance(payload, dict):
        raise error_cls(f"OpenAI {label} response must be a JSON object")

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
