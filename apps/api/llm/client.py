"""Provider-agnostic LLM client — all calls flow through AT-53 observability logging."""

from __future__ import annotations

import copy
import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from services.observability.llm_logger import LlmStage, invoke_llm

if TYPE_CHECKING:
    from services.slides.content_generation.group_a.common import (
        StructuredGenerationRequest,
        StructuredGenerator,
    )
    from services.slides.group_a_compression import GroupACompressFieldsFn
    from services.validation.constraint_validator import ConstraintViolation

DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_PROMPT_VERSION = "v1"


@dataclass(frozen=True)
class LlmUsageResult:
    payload: Any
    input_tokens: int
    output_tokens: int


class LlmClient:
    """Server-side LLM entry point. Every method records AT-53 observability metadata."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        executor: Callable[..., LlmUsageResult] | None = None,
    ) -> None:
        self._model = model
        self._executor = executor or _stub_executor

    def complete_framework(
        self,
        *,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        result = invoke_llm(
            stage=LlmStage.FRAMEWORK,
            model=self._model,
            prompt_version=prompt_version,
            retry_count=retry_count,
            call=lambda: self._executor(
                LlmStage.FRAMEWORK,
                "framework_synthesis",
                prompt_version,
                retry_count,
            ),
            input_tokens=lambda value: value.input_tokens,
            output_tokens=lambda value: value.output_tokens,
        )
        return copy.deepcopy(result.payload)

    def complete_planning(
        self,
        *,
        planning_input: dict[str, Any] | None = None,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        result = invoke_llm(
            stage=LlmStage.PLANNING,
            model=self._model,
            prompt_version=prompt_version,
            retry_count=retry_count,
            call=lambda: _invoke_executor(
                self._executor,
                LlmStage.PLANNING,
                "presentation_planner",
                prompt_version,
                retry_count,
                request=planning_input,
            ),
            input_tokens=lambda value: value.input_tokens,
            output_tokens=lambda value: value.output_tokens,
        )
        return copy.deepcopy(result.payload)

    def structured_generator(
        self,
        *,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        retry_count: int = 0,
    ) -> StructuredGenerator:
        def generate(request: StructuredGenerationRequest) -> dict[str, Any]:
            _ = request
            result = invoke_llm(
                stage=LlmStage.SLIDE_GENERATION,
                model=self._model,
                prompt_version=prompt_version,
                retry_count=retry_count,
                call=lambda: self._executor(
                    LlmStage.SLIDE_GENERATION,
                    request.layout_id,
                    prompt_version,
                    retry_count,
                ),
                input_tokens=lambda value: value.input_tokens,
                output_tokens=lambda value: value.output_tokens,
            )
            if not isinstance(result.payload, dict):
                raise TypeError("structured generator must return an object")
            return copy.deepcopy(result.payload)

        return generate

    def compression_fields_fn(
        self,
        *,
        prompt_version: str = "compression_v1",
        retry_count: int = 0,
    ) -> GroupACompressFieldsFn:
        def compress_fields(
            offending_values: dict[str, str],
            violations: list[ConstraintViolation],
        ) -> dict[str, str]:
            _ = violations
            result = invoke_llm(
                stage=LlmStage.COMPRESSION,
                model=self._model,
                prompt_version=prompt_version,
                retry_count=retry_count,
                call=lambda: self._executor(
                    LlmStage.COMPRESSION,
                    "compression",
                    prompt_version,
                    retry_count,
                ),
                input_tokens=lambda value: value.input_tokens,
                output_tokens=lambda value: value.output_tokens,
            )
            rewritten = result.payload
            if isinstance(rewritten, dict):
                return {
                    path: value
                    for path, value in rewritten.items()
                    if path in offending_values and isinstance(value, str)
                }
            return {
                path: value[: max(len(value) - 1, 0)]
                for path, value in offending_values.items()
                if len(value) > 1
            }

        return compress_fields


def _stub_executor(
    stage: LlmStage,
    operation: str,
    prompt_version: str,
    retry_count: int,
    request: dict[str, Any] | None = None,
) -> LlmUsageResult:
    _ = (stage, operation, prompt_version, retry_count, request)
    return LlmUsageResult(
        payload={"schema_version": "1.0.0", "status": "stub"},
        input_tokens=128,
        output_tokens=64,
    )


def _invoke_executor(
    executor: Callable[..., LlmUsageResult],
    stage: LlmStage,
    operation: str,
    prompt_version: str,
    retry_count: int,
    *,
    request: dict[str, Any] | None,
) -> LlmUsageResult:
    """Pass planning input to request-aware executors without breaking legacy ones."""
    arguments = (stage, operation, prompt_version, retry_count)
    if request is None:
        return executor(*arguments)

    try:
        inspect.signature(executor).bind(*arguments, request=request)
    except TypeError as exc:
        raise TypeError(
            "Planning executor must accept the confirmed Framework request payload"
        ) from exc
    except ValueError:
        pass
    return executor(*arguments, request=copy.deepcopy(request))


def load_prompt_version(path: str) -> str:
    """Return a stable prompt-version label from a prompt file path."""
    normalized = path.replace("\\", "/")
    if normalized.endswith(".txt"):
        normalized = normalized[: -len(".txt")]
    return normalized.rsplit("/", 1)[-1]
