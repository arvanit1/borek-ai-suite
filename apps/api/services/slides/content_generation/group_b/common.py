"""JJ-5..JJ-8 Group B content-generation pipeline."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

import jsonschema
from referencing import Registry, Resource

from services.slides.business_rules import (
    GroupBBusinessRuleError,
    validate_group_b_business_rules,
)
from services.slides.group_b_compression import (
    GroupBCompressFieldsFn,
    validate_and_compress_group_b_slide_spec,
)
from services.slides.source_chapter_enforcement import (
    SourceChapterValidationError,
    validate_source_chapter_ids,
)
from services.validation.compression_retry import CompressionResult

ROOT = Path(__file__).resolve().parents[6]
CONTRACTS_DIR = ROOT / "packages" / "contracts"
FRAMEWORK_SCHEMA_PATH = CONTRACTS_DIR / "framework_object.schema.json"
BASE_SLIDE_SPEC_SCHEMA_PATH = CONTRACTS_DIR / "slide_spec" / "base.schema.json"
GROUP_B_SCHEMA_DIR = CONTRACTS_DIR / "slide_spec" / "group_b"


class GroupBContentGenerationError(RuntimeError):
    """Base error for JJ-owned Group B generation failures."""


class FrameworkObjectValidationError(GroupBContentGenerationError):
    """The supplied object does not satisfy the canonical FrameworkObject contract."""


class FrameworkNotConfirmedError(GroupBContentGenerationError):
    """Stage B was requested for a FrameworkObject that is not confirmed."""


class StructuredGenerationFailure(GroupBContentGenerationError):
    """The injected structured generator failed before returning an object."""


class SlideSpecValidationError(GroupBContentGenerationError):
    """Generated content does not satisfy the canonical layout contract."""


class ProhibitedCommercialContentError(SlideSpecValidationError):
    """Presentation content contains a prohibited commercial or monetary value."""


class UngroundedContentError(SlideSpecValidationError):
    """Generated content introduces a number absent from the permitted chapters."""


class GroupBBusinessValidationError(SlideSpecValidationError, GroupBBusinessRuleError):
    """Generated content fails a Group B business rule."""


@dataclass(frozen=True)
class StructuredGenerationRequest:
    """Narrow boundary a future shared OpenAI implementation can satisfy."""

    layout_id: str
    chapters: tuple[dict[str, Any], ...]
    target_schema: dict[str, Any]
    instructions: str


StructuredGenerator = Callable[[StructuredGenerationRequest], dict[str, Any]]


@dataclass(frozen=True)
class GroupBGenerationConfig:
    layout_id: str
    schema_filename: str
    allowed_chapter_ids: tuple[str, ...]
    instructions: str


_COMMERCIAL_KEY = re.compile(
    r"(?:amount|budget|currency|investment|monetary|payback|price|pricing|revenue|roi)",
    re.IGNORECASE,
)
_CURRENCY_TEXT = re.compile(
    r"(?:[€£$]|\b(?:EUR|USD|GBP|CHF|PLN)\b|\b(?:euros?|dollars?|pounds?)\b)",
    re.IGNORECASE,
)
_COMMERCIAL_TERM = re.compile(
    r"\b(?:investment|monetary|payback|pricing?|revenue|roi|return\s+on\s+investment|budget)\b",
    re.IGNORECASE,
)
_COST_OR_SAVINGS = re.compile(r"\b(?:costs?|savings?)\b", re.IGNORECASE)
_NUMBER_TOKEN = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?%?(?![\w])")
_NON_CONTENT_KEYS = frozenset(
    {"schema_version", "slideId", "layoutId", "sourceChapterIds", "chapter_id"}
)
_DROP = object()


def generate_group_b_slide_spec(
    framework_object: dict[str, Any],
    *,
    config: GroupBGenerationConfig,
    structured_generate: StructuredGenerator,
    compress_fields: GroupBCompressFieldsFn,
) -> CompressionResult:
    """Generate, validate, and if necessary compress one Group B SlideSpec."""
    _validate_framework_object(framework_object)
    if framework_object.get("status") != "confirmed":
        raise FrameworkNotConfirmedError(
            "Stage B requires FrameworkObject.status='confirmed'"
        )

    chapters = _extract_allowed_chapters(
        framework_object,
        config.allowed_chapter_ids,
    )
    schema = _load_json(GROUP_B_SCHEMA_DIR / config.schema_filename)
    request = StructuredGenerationRequest(
        layout_id=config.layout_id,
        chapters=chapters,
        target_schema=copy.deepcopy(schema),
        instructions=config.instructions,
    )

    try:
        generated = structured_generate(request)
    except Exception as exc:
        raise StructuredGenerationFailure(
            f"Structured generation failed for {config.layout_id}: {exc}"
        ) from exc

    if not isinstance(generated, dict):
        raise SlideSpecValidationError(
            f"{config.layout_id} structured generator must return an object"
        )

    candidate = copy.deepcopy(generated)
    _validate_slide_spec(candidate, config, chapters)

    result = validate_and_compress_group_b_slide_spec(
        candidate,
        compress_fields=compress_fields,
    )
    if result.status != "VALID":
        return result

    if result.slide_spec is None:
        raise SlideSpecValidationError(
            f"{config.layout_id} validation returned no SlideSpec"
        )
    _validate_slide_spec(result.slide_spec, config, chapters)
    return result


def _validate_framework_object(framework_object: Any) -> None:
    if not isinstance(framework_object, dict):
        raise FrameworkObjectValidationError("FrameworkObject must be an object")
    try:
        _framework_validator().validate(framework_object)
    except jsonschema.ValidationError as exc:
        path = _json_path(exc.absolute_path)
        raise FrameworkObjectValidationError(
            f"Invalid FrameworkObject at {path}: {exc.message}"
        ) from exc


def _extract_allowed_chapters(
    framework_object: dict[str, Any],
    allowed_chapter_ids: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    chapters_by_id = {
        chapter["chapter_id"]: chapter
        for chapter in framework_object["chapters"]
    }
    selected: list[dict[str, Any]] = []
    for chapter_id in allowed_chapter_ids:
        chapter = chapters_by_id.get(chapter_id)
        if chapter is None:
            raise FrameworkObjectValidationError(
                f"FrameworkObject is missing required chapter {chapter_id}"
            )
        selected_chapter = {
            "chapter_id": chapter["chapter_id"],
            "title": chapter["title"],
            "body": copy.deepcopy(chapter["body"]),
        }
        selected_chapter["body"] = _sanitize_commercial_value(
            selected_chapter["body"]
        )
        selected.append(selected_chapter)
    return tuple(selected)


def _sanitize_commercial_value(value: Any) -> Any:
    sanitized = _sanitize_commercial_node(value)
    if sanitized is _DROP:
        return ""
    return sanitized


def _sanitize_commercial_node(value: Any) -> Any:
    if isinstance(value, str):
        return _DROP if _contains_commercial_value(value) else value
    if isinstance(value, list):
        sanitized_items = []
        for item in value:
            sanitized = _sanitize_commercial_node(item)
            if sanitized is not _DROP:
                sanitized_items.append(sanitized)
        return sanitized_items
    if isinstance(value, dict):
        sanitized_object: dict[str, Any] = {}
        for key, item in value.items():
            if _COMMERCIAL_KEY.search(str(key)):
                continue
            sanitized = _sanitize_commercial_node(item)
            if sanitized is not _DROP:
                sanitized_object[key] = sanitized
        return sanitized_object
    return copy.deepcopy(value)


def _validate_slide_spec(
    slide_spec: dict[str, Any],
    config: GroupBGenerationConfig,
    chapters: tuple[dict[str, Any], ...],
) -> None:
    try:
        _slide_validator(config.schema_filename).validate(slide_spec)
    except jsonschema.ValidationError as exc:
        path = _json_path(exc.absolute_path)
        raise SlideSpecValidationError(
            f"Invalid {config.layout_id} SlideSpec at {path}: {exc.message}"
        ) from exc

    validate_source_chapter_ids(
        slide_spec,
        allowed_chapter_ids=config.allowed_chapter_ids,
        layout_id=config.layout_id,
    )

    commercial_paths = _find_commercial_paths(slide_spec)
    if commercial_paths:
        raise ProhibitedCommercialContentError(
            f"{config.layout_id} contains prohibited commercial content at "
            f"{commercial_paths[0]}"
        )

    cited_chapters = tuple(
        chapter
        for chapter in chapters
        if chapter["chapter_id"] in slide_spec["sourceChapterIds"]
    )
    _validate_numeric_grounding(slide_spec, cited_chapters, config.layout_id)

    try:
        validate_group_b_business_rules(slide_spec)
    except GroupBBusinessRuleError as exc:
        raise GroupBBusinessValidationError(str(exc)) from exc


def _find_commercial_paths(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, str):
        if _contains_commercial_value(value):
            hits.append(path)
        return hits
    if isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_find_commercial_paths(item, f"{path}[{index}]"))
        return hits
    if isinstance(value, dict):
        for key, item in value.items():
            hits.extend(_find_commercial_paths(item, f"{path}.{key}"))
    return hits


def _contains_commercial_value(text: str) -> bool:
    if _CURRENCY_TEXT.search(text) or _COMMERCIAL_TERM.search(text):
        return True
    return bool(_COST_OR_SAVINGS.search(text) and _NUMBER_TOKEN.search(text))


def _validate_numeric_grounding(
    slide_spec: dict[str, Any],
    chapters: tuple[dict[str, Any], ...],
    layout_id: str,
) -> None:
    grounded_numbers = _number_tokens(chapters)
    generated_numbers = _number_tokens(slide_spec)
    invented = sorted(generated_numbers - grounded_numbers)
    if invented:
        raise UngroundedContentError(
            f"{layout_id} contains numeric content absent from its allowed chapters: "
            f"{invented[0]}"
        )


def _number_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    for text in _iter_content_strings(value):
        for match in _NUMBER_TOKEN.finditer(text):
            tokens.add(match.group(0).rstrip("%").replace(",", "."))
    return tokens


def _iter_content_strings(value: Any):
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_content_strings(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key not in _NON_CONTENT_KEYS:
                yield from _iter_content_strings(item)


@lru_cache(maxsize=1)
def _framework_validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(_load_json(FRAMEWORK_SCHEMA_PATH))


@lru_cache(maxsize=None)
def _slide_validator(schema_filename: str) -> jsonschema.Draft202012Validator:
    schema = _load_json(GROUP_B_SCHEMA_DIR / schema_filename)
    base_schema = _load_json(BASE_SLIDE_SPEC_SCHEMA_PATH)
    base_resource = Resource.from_contents(base_schema)
    relative_base_uri = urljoin(schema["$id"], "../base.schema.json")
    registry = (
        Registry()
        .with_resource(base_schema["$id"], base_resource)
        .with_resource(relative_base_uri, base_resource)
    )
    return jsonschema.Draft202012Validator(schema, registry=registry)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_path(parts: Any) -> str:
    path = "$"
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path
