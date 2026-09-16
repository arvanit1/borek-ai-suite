"""Shared MS-6..MS-10 Group C content-generation pipeline."""

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
    ArchitectureMinComponentsError,
    ProhibitedCurrencyContentError,
    reject_success_metrics_currency,
    validate_architecture_min_components,
)
from services.slides.group_c_compression import (
    GroupCCompressFieldsFn,
    validate_and_compress_group_c_slide_spec,
)
from services.framework.customer_view import presentation_chapter_excerpt
from services.validation.compression_retry import CompressionResult
from services.validation.compression_retry import get_value_at_path, set_value_at_path
from services.validation.source_chapter_enforcement import (
    SourceChapterEnforcementError,
    populated_content_leaf_paths,
    validate_field_provenance,
)

ROOT = Path(__file__).resolve().parents[6]
CONTRACTS_DIR = ROOT / "packages" / "contracts"
FRAMEWORK_SCHEMA_PATH = CONTRACTS_DIR / "framework_object.schema.json"
BASE_SLIDE_SPEC_SCHEMA_PATH = CONTRACTS_DIR / "slide_spec" / "base.schema.json"
GROUP_C_SCHEMA_DIR = CONTRACTS_DIR / "slide_spec" / "group_c"


class GroupCContentGenerationError(RuntimeError):
    """Base error for MS-owned Group C generation failures."""


class FrameworkObjectValidationError(GroupCContentGenerationError):
    """The supplied object does not satisfy the canonical FrameworkObject contract."""


class FrameworkNotConfirmedError(GroupCContentGenerationError):
    """Stage B was requested for a FrameworkObject that is not confirmed."""


class StructuredGenerationFailure(GroupCContentGenerationError):
    """The injected structured generator failed before returning an object."""


class SlideSpecValidationError(GroupCContentGenerationError):
    """Generated content does not satisfy the canonical layout contract."""


class SourceChapterValidationError(SlideSpecValidationError):
    """Generated provenance does not match the layout's allowed Framework chapters."""


class ProhibitedCommercialContentError(SlideSpecValidationError):
    """Presentation content contains a prohibited commercial or monetary value."""


class UngroundedContentError(SlideSpecValidationError):
    """Generated content introduces a number absent from its attributed chapters."""


class GroupCBusinessValidationError(SlideSpecValidationError):
    """Generated content fails a Group C business rule (MS-13 / MS-14)."""


@dataclass(frozen=True)
class StructuredGenerationRequest:
    """Narrow boundary a future shared OpenAI implementation can satisfy."""

    layout_id: str
    chapters: tuple[dict[str, Any], ...]
    target_schema: dict[str, Any]
    instructions: str


StructuredGenerator = Callable[[StructuredGenerationRequest], dict[str, Any]]
_MAX_AT8_REGENERATION_ATTEMPTS = 3


@dataclass(frozen=True)
class GroupCGenerationConfig:
    layout_id: str
    schema_filename: str
    allowed_chapter_ids: tuple[str, ...]
    provenance_path_guidance: str
    instructions: str
    exclude_monetary_fields: bool = False


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
    {
        "schema_version",
        "slideId",
        "layoutId",
        "sourceChapterIds",
        "fieldProvenance",
        "chapter_id",
    }
)
_DROP = object()
_OPTIONAL_MONETARY_EXCLUSION_FIELDS = frozenset({"subtitle", "sectionLabel"})
_EXCLUDED_MONETARY_PROMPT = (
    " Monetary exclusion is active (excludeMonetaryFields=true). Do not include "
    "prices, costs, savings amounts, ROI, revenue, commercial claims, fees, "
    "budgets, currency values, monetary percentages, payback, investment, or "
    "pricing language in any generated field, including title, subtitle, "
    "sectionLabel, criteria titles, criteria descriptions, and callouts."
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def generate_group_c_slide_spec(
    framework_object: dict[str, Any],
    *,
    config: GroupCGenerationConfig,
    structured_generate: StructuredGenerator,
    compress_fields: GroupCCompressFieldsFn,
) -> CompressionResult:
    """Generate, validate, and if necessary compress one Group C SlideSpec.

    The injected generator receives only the configured Framework chapters, the
    canonical target schema, and layout-specific grounding instructions. No transcript,
    provider credentials, model configuration, or networking concern enters this layer.
    """
    _validate_framework_object(framework_object)
    if framework_object.get("status") != "confirmed":
        raise FrameworkNotConfirmedError(
            "Stage B requires FrameworkObject.status='confirmed'"
        )

    chapters = _extract_allowed_chapters(
        framework_object,
        config.allowed_chapter_ids,
    )
    schema = _load_json(GROUP_C_SCHEMA_DIR / config.schema_filename)
    request = StructuredGenerationRequest(
        layout_id=config.layout_id,
        chapters=chapters,
        target_schema=copy.deepcopy(schema),
        instructions=_generation_instructions(config),
    )

    result: CompressionResult | None = None
    for attempt in range(_MAX_AT8_REGENERATION_ATTEMPTS):
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
        if config.exclude_monetary_fields:
            candidate = repair_excluded_monetary_content(
                candidate,
                chapters=chapters,
            )
        try:
            _validate_slide_spec(candidate, config, chapters)
        except UngroundedContentError as exc:
            if attempt + 1 < _MAX_AT8_REGENERATION_ATTEMPTS:
                request = _with_at8_rejection(request, str(exc))
                continue
            raise
        except (ProhibitedCommercialContentError, GroupCBusinessValidationError) as exc:
            if (
                config.exclude_monetary_fields
                and attempt + 1 < _MAX_AT8_REGENERATION_ATTEMPTS
            ):
                request = _with_at8_rejection(request, str(exc))
                continue
            raise
        result = validate_and_compress_group_c_slide_spec(
            candidate,
            compress_fields=compress_fields,
        )
        if result.status == "VALID":
            break
        if attempt + 1 < _MAX_AT8_REGENERATION_ATTEMPTS and result.message:
            request = _with_at8_rejection(request, result.message)

    if result is None:
        raise SlideSpecValidationError(
            f"{config.layout_id} validation returned no result"
        )
    if result.status != "VALID":
        return result

    if result.slide_spec is None:
        raise SlideSpecValidationError(
            f"{config.layout_id} validation returned no SlideSpec"
        )
    _validate_slide_spec(result.slide_spec, config, chapters)
    return result


def _with_at8_rejection(
    request: StructuredGenerationRequest,
    message: str,
) -> StructuredGenerationRequest:
    extra = (
        f"\n\nYour previous SlideSpec was rejected: {message} "
        "Honor every maxLength and maxItems limit. Rewrite overflowing "
        "fields as complete shorter phrases. Do not clip with an ellipsis "
        "or invent facts."
    )
    return StructuredGenerationRequest(
        layout_id=request.layout_id,
        chapters=request.chapters,
        target_schema=request.target_schema,
        instructions=f"{request.instructions}{extra}",
    )


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
        if chapter_id not in chapters_by_id:
            raise FrameworkObjectValidationError(
                f"FrameworkObject is missing required chapter {chapter_id}"
            )
        selected_chapter = presentation_chapter_excerpt(framework_object, str(chapter_id))
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
    config: GroupCGenerationConfig,
    chapters: tuple[dict[str, Any], ...],
) -> None:
    try:
        _slide_validator(config.schema_filename).validate(slide_spec)
    except jsonschema.ValidationError as exc:
        path = _json_path(exc.absolute_path)
        raise SlideSpecValidationError(
            f"Invalid {config.layout_id} SlideSpec at {path}: {exc.message}"
        ) from exc

    source_chapter_ids = slide_spec.get("sourceChapterIds")
    if (
        not isinstance(source_chapter_ids, list)
        or not source_chapter_ids
        or len(set(source_chapter_ids)) != len(source_chapter_ids)
        or not set(source_chapter_ids).issubset(config.allowed_chapter_ids)
    ):
        raise SourceChapterValidationError(
            f"{config.layout_id}.sourceChapterIds must be a non-empty, duplicate-free "
            f"subset of allowed chapters {list(config.allowed_chapter_ids)}"
        )

    try:
        provenance_by_path = validate_field_provenance(
            slide_spec,
            real_chapter_ids=(chapter["chapter_id"] for chapter in chapters),
            allowed_chapter_ids=config.allowed_chapter_ids,
        )
    except SourceChapterEnforcementError as exc:
        raise SourceChapterValidationError(
            f"Invalid {config.layout_id} field provenance: {exc}"
        ) from exc

    commercial_paths = _find_commercial_paths(slide_spec)
    if commercial_paths:
        raise ProhibitedCommercialContentError(
            f"{config.layout_id} contains prohibited commercial content at "
            f"{commercial_paths[0]}"
        )

    _validate_numeric_grounding(
        slide_spec,
        chapters,
        config.layout_id,
        provenance_by_path,
    )

    try:
        validate_architecture_min_components(slide_spec)
        reject_success_metrics_currency(slide_spec)
    except (ArchitectureMinComponentsError, ProhibitedCurrencyContentError) as exc:
        raise GroupCBusinessValidationError(str(exc)) from exc


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
            if key in _NON_CONTENT_KEYS:
                continue
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
    provenance_by_path: dict[str, tuple[str, ...]],
) -> None:
    chapters_by_id = {chapter["chapter_id"]: chapter for chapter in chapters}
    for path, source_chapter_ids in provenance_by_path.items():
        generated_numbers = _number_tokens(get_value_at_path(slide_spec, path))
        if not generated_numbers:
            continue
        attributed_chapters = tuple(
            chapters_by_id[chapter_id] for chapter_id in source_chapter_ids
        )
        grounded_numbers = _number_tokens(attributed_chapters)
        invented = sorted(generated_numbers - grounded_numbers)
        if invented:
            raise UngroundedContentError(
                f"{layout_id} contains numeric content at {path} absent from its "
                f"field-attributed chapters: {invented[0]}"
            )


def repair_excluded_monetary_content(
    slide_spec: dict[str, Any],
    *,
    chapters: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Remove or rewrite prohibited commercial copy before ES-39 validation."""
    repaired = copy.deepcopy(slide_spec)
    for _ in range(32):
        commercial_paths = _find_commercial_paths(repaired)
        if not commercial_paths:
            break
        path = commercial_paths[0]
        field_name = path.rsplit(".", 1)[-1].split("[", 1)[0]
        if field_name in _OPTIONAL_MONETARY_EXCLUSION_FIELDS:
            _remove_value_at_path(repaired, path)
            _prune_field_provenance(repaired, path)
            continue

        current = get_value_at_path(repaired, _path_for_accessor(path))
        if not isinstance(current, str):
            break
        cleaned = _repair_commercial_string(current, chapters=chapters)
        if cleaned and not _contains_commercial_value(cleaned):
            set_value_at_path(repaired, _path_for_accessor(path), cleaned)
            continue
        fallback = _grounded_non_commercial_fallback(chapters)
        if fallback and not _contains_commercial_value(fallback):
            set_value_at_path(repaired, _path_for_accessor(path), fallback)
            continue
        break

    _prune_field_provenance(repaired)
    return repaired


def _path_for_accessor(path: str) -> str:
    return path[2:] if path.startswith("$.") else path


def _remove_value_at_path(payload: dict[str, Any], path: str) -> None:
    accessor = _path_for_accessor(path)
    from services.validation.compression_retry import _parse_path_tokens

    tokens = list(_parse_path_tokens(accessor))
    if not tokens:
        raise KeyError(path)
    current: Any = payload
    for segment, index, quoted in tokens[:-1]:
        if segment is not None:
            current = current[segment]
        elif index is not None:
            current = current[int(index)]
        else:
            current = current[quoted]  # type: ignore[index]

    last_segment, last_index, last_quoted = tokens[-1]
    if last_segment is not None:
        current.pop(last_segment, None)
    elif last_index is not None:
        del current[int(last_index)]
    else:
        del current[last_quoted]  # type: ignore[index]


def _prune_field_provenance(
    slide_spec: dict[str, Any],
    removed_path: str | None = None,
) -> None:
    provenance = slide_spec.get("fieldProvenance")
    if not isinstance(provenance, list):
        return
    expected = set(populated_content_leaf_paths(slide_spec))
    normalized_removed = (
        _path_for_accessor(removed_path) if removed_path is not None else None
    )
    slide_spec["fieldProvenance"] = [
        entry
        for entry in provenance
        if isinstance(entry, dict)
        and entry.get("path") in expected
        and (
            normalized_removed is None or entry.get("path") != normalized_removed
        )
    ]


def _repair_commercial_string(
    text: str,
    *,
    chapters: tuple[dict[str, Any], ...],
) -> str:
    cleaned_parts = [
        part.strip()
        for part in _SENTENCE_SPLIT.split(text.strip())
        if part.strip() and not _contains_commercial_value(part.strip())
    ]
    if cleaned_parts:
        return " ".join(cleaned_parts)
    return ""


def _grounded_non_commercial_fallback(
    chapters: tuple[dict[str, Any], ...],
) -> str | None:
    for chapter in chapters:
        title = chapter.get("title")
        if isinstance(title, str) and title.strip() and not _contains_commercial_value(title):
            return title.strip()
    for chapter in chapters:
        for text in _iter_content_strings(chapter.get("body", {})):
            if (
                isinstance(text, str)
                and len(text.strip()) >= 3
                and not _contains_commercial_value(text)
            ):
                return text.strip()
    return None


def _generation_instructions(config: GroupCGenerationConfig) -> str:
    from llm.json_schema_bundle import layout_limit_instruction

    allowed = ", ".join(config.allowed_chapter_ids)
    monetary_rule = _EXCLUDED_MONETARY_PROMPT if config.exclude_monetary_fields else ""
    return (
        f"{config.instructions}{monetary_rule}{layout_limit_instruction(config.layout_id)} "
        "Include fieldProvenance in the generated SlideSpec. "
        "Use the same dotted/array path syntax as AT-8 (for example, "
        "components[0].title or left.items[0]). Include exactly one provenance "
        "entry for every populated Framework-derived content leaf and no entries for "
        "metadata or nonexistent fields. Metadata exemptions are schema_version, "
        "layoutId, slideId, root sourceChapterIds, and fieldProvenance. "
        f"Required content paths for this layout are: {config.provenance_path_guidance}. "
        f"Every field-level sourceChapterIds list must be non-empty, unique, and use "
        f"only allowed chapters [{allowed}]. Root sourceChapterIds must equal the union "
        "of all field-level sourceChapterIds. Attribute each field only to the chapters "
        "that actually support it; do not copy the full root list onto every field."
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
    schema = _load_json(GROUP_C_SCHEMA_DIR / schema_filename)
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
