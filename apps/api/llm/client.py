"""Provider-agnostic LLM client — all calls flow through AT-53 observability logging."""

from __future__ import annotations

import copy
import inspect
import re
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
_NUMBER_TOKEN = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?%?(?![\w])")
_COMPRESSION_NUMBER_RULE = (
    "NUMBERS: Keep every digit token in the exact form already present in the "
    "supplied field text. Write '1.200' not '1200', 'three-way' not '3-way', "
    "'three' not '3'. Do not introduce any digit that is not already in that field."
)


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
            payload = {
                "instructions": request.instructions,
                "layoutId": request.layout_id,
                "chapters": [copy.deepcopy(chapter) for chapter in request.chapters],
                "targetSchema": copy.deepcopy(request.target_schema),
            }
            result = invoke_llm(
                stage=LlmStage.SLIDE_GENERATION,
                model=self._model,
                prompt_version=prompt_version,
                retry_count=retry_count,
                call=lambda: _invoke_executor(
                    self._executor,
                    LlmStage.SLIDE_GENERATION,
                    request.layout_id,
                    prompt_version,
                    retry_count,
                    request=payload,
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
        instructions: str | None = None,
    ) -> GroupACompressFieldsFn:
        prompt_instructions = instructions or (
            "Rewrite only the supplied offending string fields so each satisfies "
            "its max_length limit. Return a JSON object mapping the same paths to "
            "shortened strings. Do not add paths, invent facts, or change meaning."
        )

        def compress_fields(
            offending_values: dict[str, str],
            violations: list[ConstraintViolation],
        ) -> dict[str, str]:
            if not offending_values:
                return {}
            limits = _max_length_by_path(violations)
            properties = {
                path: _compression_string_schema(path, limits.get(path))
                for path in offending_values
            }
            limit_lines = [
                f"- {path}: at most {limits[path]} characters (currently {len(offending_values[path])})"
                for path in offending_values
                if path in limits
            ]
            bound_instructions = f"{prompt_instructions}\n\n{_COMPRESSION_NUMBER_RULE}"
            if limit_lines:
                bound_instructions = (
                    f"{bound_instructions}\n\nHard limits:\n" + "\n".join(limit_lines)
                )
            payload = {
                "instructions": bound_instructions,
                "offendingValues": copy.deepcopy(offending_values),
                "violations": [_violation_payload(item) for item in violations],
                "targetSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": properties,
                    "required": list(offending_values),
                },
            }
            result = invoke_llm(
                stage=LlmStage.COMPRESSION,
                model=self._model,
                prompt_version=prompt_version,
                retry_count=retry_count,
                call=lambda: _invoke_executor(
                    self._executor,
                    LlmStage.COMPRESSION,
                    "compression",
                    prompt_version,
                    retry_count,
                    request=payload,
                ),
                input_tokens=lambda value: value.input_tokens,
                output_tokens=lambda value: value.output_tokens,
            )
            rewritten = result.payload
            if isinstance(rewritten, dict):
                fitted = {
                    path: value
                    for path, value in rewritten.items()
                    if path in offending_values and isinstance(value, str)
                }
            else:
                fitted = {
                    path: value
                    for path, value in offending_values.items()
                    if isinstance(value, str)
                }
            return {
                path: _fit_max_length(
                    _spell_introduced_number_tokens(
                        offending_values[path],
                        _restore_source_number_forms(offending_values[path], value),
                    ),
                    limits.get(path),
                )
                for path, value in fitted.items()
            }

        return compress_fields


def ungrounded_content_retry_instruction(
    *,
    field_path: str,
    ungrounded_tokens: set[str],
    attributed_chapter_ids: list[str] | tuple[str, ...],
    allowed_chapter_ids: list[str] | tuple[str, ...],
) -> str:
    """AT-8-adjacent retry text when BT-14 rejects an ungrounded digit token."""
    return (
        f"The field '{field_path}' contains a number token "
        f"({ungrounded_tokens}) that does not appear in the "
        f"body text of its attributed chapters "
        f"({attributed_chapter_ids}). This means you wrote "
        f"a digit that is not grounded in the source text. "
        f"Rewrite '{field_path}' using only words — spell "
        f"out any numbers ('three-way' not '3-way', "
        f"'three' not '3'). Do not introduce any digit "
        f"that is not present as a digit in the chapter "
        f"text you were given. Do not cite any chapter "
        f"not in {allowed_chapter_ids}."
    )


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
            "LLM executor must accept the structured request payload"
        ) from exc
    except ValueError:
        pass
    return executor(*arguments, request=copy.deepcopy(request))


def _violation_payload(violation: Any) -> dict[str, Any]:
    return {
        "path": getattr(violation, "path", None),
        "code": getattr(violation, "code", None),
        "message": getattr(violation, "message", None),
        "limit": getattr(violation, "limit", None),
    }


def _max_length_by_path(violations: list[Any]) -> dict[str, int]:
    limits: dict[str, int] = {}
    for violation in violations:
        path = getattr(violation, "path", None)
        limit = getattr(violation, "limit", None)
        if isinstance(path, str) and isinstance(limit, int) and limit > 0:
            limits[path] = limit
    return limits


def _compression_string_schema(path: str, limit: int | None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string"}
    if limit is not None:
        schema["maxLength"] = limit
        schema["description"] = f"{path} must be at most {limit} characters."
    return schema


def _normalize_number_token(token: str) -> str:
    return token.rstrip("%").replace(",", ".")


def _number_token_set(text: str) -> set[str]:
    return {_normalize_number_token(match.group(0)) for match in _NUMBER_TOKEN.finditer(text)}


def _spell_introduced_number_tokens(original: str, rewritten: str) -> str:
    """Spell out digits that AT-8 introduced and that were not in the source field."""
    introduced = _number_token_set(rewritten) - _number_token_set(original)
    if not introduced:
        return rewritten
    from llm.live_slide_repair import _sanitize_ungrounded_digit_compounds

    return _sanitize_ungrounded_digit_compounds(rewritten, {}, introduced)


def _restore_source_number_forms(original: str, rewritten: str) -> str:
    """Keep source digit forms so AT-8 shortening cannot invent 1200 from 1.200."""
    originals = _number_token_set(original)

    def replace(match: re.Match[str]) -> str:
        raw = match.group(0)
        normalized = _normalize_number_token(raw)
        if normalized in originals:
            return raw
        digits = re.sub(r"[.,]", "", normalized)
        for source in originals:
            if digits and digits == re.sub(r"[.,]", "", source):
                return f"{source}%" if raw.endswith("%") else source
        return raw

    return _NUMBER_TOKEN.sub(replace, rewritten)


def _fit_max_length(value: str, limit: int | None) -> str:
    """Honor AT-8's 'no mid-word cut' if the model still ignores maxLength."""
    if limit is None or len(value) <= limit:
        return value
    clipped = value[:limit].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0].rstrip()
    return clipped or value[:limit]


def load_prompt_version(path: str) -> str:
    """Return a stable prompt-version label from a prompt file path."""
    normalized = path.replace("\\", "/")
    if normalized.endswith(".txt"):
        normalized = normalized[: -len(".txt")]
    return normalized.rsplit("/", 1)[-1]
