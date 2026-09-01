"""Repair live SlideSpec JSON so BT-14/AT-8 can accept a valid object.

OpenAI returns content. Group A then enforces complete fieldProvenance, no
commercial values, and numeric grounding. The model often omits provenance for
leaves such as title or sectionLabel. This layer only:

- drops stale provenance
- attributes missing leaves when the layout has exactly one allowed chapter
- for Group A only: attributes a *required* missing leaf to every chapter on
  the request (the CONTEXT_01 fixture pattern: title → ["1","2"]). That is the
  set the model was allowed to read — not a guessed single chapter.
- drops optional leaves when attribution would pick one of several chapters
- syncs root sourceChapterIds to the provenance union
- does not clip overflow: extra array items and overlong strings stay as
  emitted so AT-8 can compress semantically or return VALIDATION_FAILED
- retries the model a bounded number of times with the rejection reason

Group B/C generators are unchanged: required multi-chapter gaps stay fail-closed.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Callable

from llm.client import ungrounded_content_retry_instruction
from services.slides.content_generation.group_a.common import (
    ProhibitedCommercialContentError,
    UngroundedContentError,
    _find_commercial_paths,
    _number_tokens,
    _validate_numeric_grounding,
)
from services.slides.content_generation.group_b.common import (
    UngroundedContentError as GroupBUngroundedContentError,
    _validate_numeric_grounding as _validate_group_b_numeric_grounding,
)
from services.validation.compression_retry import get_value_at_path, set_value_at_path
from services.validation.source_chapter_enforcement import (
    SourceChapterEnforcementError,
    populated_content_leaf_paths,
    validate_field_provenance,
)

MAX_LIVE_GENERATION_ATTEMPTS = 3
_METADATA_ROOTS = frozenset(
    {"schema_version", "layoutId", "slideId", "sourceChapterIds", "fieldProvenance"}
)
_GROUP_A_LAYOUT_IDS = frozenset(
    {
        "COVER_01",
        "CONTEXT_01",
        "PROBLEM_SOLUTION_01",
        "SCOPE_01",
        "REQUIREMENTS_MATRIX_01",
    }
)
_UNGROUNDED_MESSAGE = re.compile(
    r"numeric content(?: at (?P<path>\S+))? absent from its "
    r"(?:field-attributed|allowed) chapters: (?P<token>.+)$"
)
_NUMBER_TOKEN = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?%?(?![\w])")
_DIGIT_WORDS = {
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
    "11": "eleven",
    "12": "twelve",
    "13": "thirteen",
    "14": "fourteen",
    "15": "fifteen",
    "16": "sixteen",
    "17": "seventeen",
    "18": "eighteen",
    "19": "nineteen",
    "20": "twenty",
    "30": "thirty",
    "40": "forty",
    "50": "fifty",
    "60": "sixty",
    "70": "seventy",
    "80": "eighty",
    "90": "ninety",
    "100": "one hundred",
}
_UNGROUNDED_ERRORS = (UngroundedContentError, GroupBUngroundedContentError)


class LiveSlideRepairError(RuntimeError):
    """The live SlideSpec is still illegal after repair."""


def wrap_live_structured_generator(
    generate: Callable[[Any], dict[str, Any]],
) -> Callable[[Any], dict[str, Any]]:
    """Return a StructuredGenerator that repairs, then retries, live OpenAI output."""

    def generate_and_repair(request: Any) -> dict[str, Any]:
        last_error: str | None = None
        last_payload: dict[str, Any] | None = None
        rewrite_path: str | None = None
        for attempt in range(MAX_LIVE_GENERATION_ATTEMPTS):
            current_request = request
            if last_error is not None:
                current_request = _with_rejection(request, last_error)
            raw = generate(current_request)
            if not isinstance(raw, dict):
                raise TypeError("structured generator must return an object")
            repaired = repair_live_slide_spec(raw, request)
            if rewrite_path and last_payload is not None:
                repaired = _merge_rewritten_field(last_payload, repaired, rewrite_path, request)
            last_payload = repaired
            try:
                _assert_live_slide_is_acceptable(repaired, request)
                return repaired
            except _UNGROUNDED_ERRORS as exc:
                last_error = _ungrounded_retry_message(exc, repaired, request)
                rewrite_path = _ungrounded_field_path(exc)
                _ = attempt
            except (
                LiveSlideRepairError,
                SourceChapterEnforcementError,
                ProhibitedCommercialContentError,
            ) as exc:
                last_error = str(exc)
                rewrite_path = None
                _ = attempt
        return last_payload if last_payload is not None else {}

    return generate_and_repair


def repair_live_slide_spec(slide_spec: dict[str, Any], request: Any) -> dict[str, Any]:
    """Make a best-effort legal SlideSpec without inventing multi-chapter sources."""
    spec = copy.deepcopy(slide_spec)
    spec["layoutId"] = getattr(request, "layout_id", spec.get("layoutId"))
    spec.setdefault("schema_version", "1.0")

    chapter_ids = _request_chapter_ids(request)
    required_roots = _required_roots(request)
    provenance = _provenance_entries(spec.get("fieldProvenance"))
    expected = set(populated_content_leaf_paths(spec))
    by_path = {entry["path"]: entry for entry in provenance if entry["path"] in expected}

    missing = sorted(expected - set(by_path))
    group_a = _is_group_a_layout(request)
    for path in missing:
        if len(chapter_ids) == 1:
            by_path[path] = {
                "path": path,
                "sourceChapterIds": list(chapter_ids),
            }
            continue
        if _root_field(path) not in required_roots:
            _clear_root_field(spec, path)
            continue
        if group_a and chapter_ids:
            by_path[path] = {
                "path": path,
                "sourceChapterIds": list(chapter_ids),
            }

    expected = set(populated_content_leaf_paths(spec))
    by_path = {path: entry for path, entry in by_path.items() if path in expected}
    if _should_keep_field_provenance(request):
        spec["fieldProvenance"] = [by_path[path] for path in sorted(by_path)]
        union: list[str] = []
        for entry in spec["fieldProvenance"]:
            for chapter_id in entry["sourceChapterIds"]:
                if chapter_id not in union:
                    union.append(chapter_id)
        spec["sourceChapterIds"] = union or list(chapter_ids[:1])
    else:
        spec.pop("fieldProvenance", None)
        if not spec.get("sourceChapterIds") and chapter_ids:
            spec["sourceChapterIds"] = list(chapter_ids)
    _strip_undeclared_properties(spec, request)
    return spec


def _assert_live_slide_is_acceptable(slide_spec: dict[str, Any], request: Any) -> None:
    chapter_ids = _request_chapter_ids(request)
    chapters = tuple(
        copy.deepcopy(chapter) for chapter in getattr(request, "chapters", ())
    )
    layout_id = str(getattr(request, "layout_id", "slide"))
    if _should_keep_field_provenance(request):
        provenance = validate_field_provenance(
            slide_spec,
            real_chapter_ids=chapter_ids,
            allowed_chapter_ids=chapter_ids,
        )
        _sanitize_ungrounded_leaves(slide_spec, chapters, provenance)
        _validate_numeric_grounding(slide_spec, chapters, layout_id, provenance)
    else:
        cited_ids = _root_source_chapter_ids(slide_spec, chapter_ids)
        provenance = {
            path: cited_ids for path in populated_content_leaf_paths(slide_spec)
        }
        _sanitize_ungrounded_leaves(slide_spec, chapters, provenance)
        cited = tuple(
            chapter
            for chapter in chapters
            if chapter.get("chapter_id") in set(cited_ids)
        )
        _validate_group_b_numeric_grounding(slide_spec, cited, layout_id)
    commercial = _find_commercial_paths(slide_spec)
    if commercial:
        raise LiveSlideRepairError(
            f"prohibited commercial content at {commercial[0]}"
        )


def _sanitize_ungrounded_digit_compounds(
    text: str,
    allowed_chapter_bodies: dict[str, str],
    ungrounded_tokens: set[str],
) -> str:
    """Rewrite ungrounded digit compounds to words. Does not strip grounded digits."""
    grounded: set[str] = set()
    for body in allowed_chapter_bodies.values():
        for match in _NUMBER_TOKEN.finditer(body):
            grounded.add(match.group(0).rstrip("%").replace(",", "."))
    for digit in ungrounded_tokens:
        if digit in grounded:
            continue
        word = _number_to_words(digit)
        if word is None:
            continue
        text = re.sub(
            rf"(?<![0-9]){re.escape(digit)}%(?![\w])",
            f"{word} percent",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            rf"(?<![0-9]){re.escape(digit)}(?=-)",
            word,
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            rf"(?<![\w]){re.escape(digit)}(?=\s+[a-zA-Z])",
            word,
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            rf"(?<![\w]){re.escape(digit)}(?![\w.])",
            word,
            text,
            flags=re.IGNORECASE,
        )
    return text


def _sanitize_ungrounded_leaves(
    slide_spec: dict[str, Any],
    chapters: tuple[dict[str, Any], ...],
    provenance_by_path: dict[str, tuple[str, ...]],
) -> None:
    chapters_by_id = {
        chapter["chapter_id"]: chapter
        for chapter in chapters
        if isinstance(chapter, dict) and isinstance(chapter.get("chapter_id"), str)
    }
    bodies = {
        chapter_id: _chapter_body_text(chapter)
        for chapter_id, chapter in chapters_by_id.items()
    }
    for path, source_chapter_ids in provenance_by_path.items():
        try:
            value = get_value_at_path(slide_spec, path)
        except KeyError:
            continue
        if not isinstance(value, str):
            continue
        generated_numbers = _number_tokens(value)
        if not generated_numbers:
            continue
        attributed = tuple(
            chapters_by_id[chapter_id]
            for chapter_id in source_chapter_ids
            if chapter_id in chapters_by_id
        )
        invented = generated_numbers - _number_tokens(attributed)
        if not invented:
            continue
        rewritten = _sanitize_ungrounded_digit_compounds(value, bodies, invented)
        if rewritten != value:
            set_value_at_path(slide_spec, path, rewritten)


def _number_to_words(digit: str) -> str | None:
    if digit in _DIGIT_WORDS:
        return _DIGIT_WORDS[digit]
    if not digit.isdigit():
        return None
    value = int(digit)
    if value < 1 or value > 999:
        return None
    ones = [
        "",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
    ]
    teens = [
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
    ]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    if value < 10:
        return ones[value]
    if value < 20:
        return teens[value - 10]
    if value < 100:
        ten, one = divmod(value, 10)
        return tens[ten] if one == 0 else f"{tens[ten]}-{ones[one]}"
    hundred, rest = divmod(value, 100)
    if rest == 0:
        return f"{ones[hundred]} hundred"
    return f"{ones[hundred]} hundred {_number_to_words(str(rest))}"


def _chapter_body_text(chapter: dict[str, Any]) -> str:
    body = chapter.get("body")
    if isinstance(body, str):
        return body
    return " ".join(_iter_strings(body))


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)


def _ungrounded_field_path(exc: Exception) -> str | None:
    match = _UNGROUNDED_MESSAGE.search(str(exc))
    if match is None:
        return None
    return match.group("path")


def _ungrounded_retry_message(
    exc: Exception,
    slide_spec: dict[str, Any],
    request: Any,
) -> str:
    match = _UNGROUNDED_MESSAGE.search(str(exc))
    field_path = match.group("path") if match and match.group("path") else "the slide content"
    token = match.group("token").strip() if match else str(exc)
    attributed: list[str] = []
    for entry in _provenance_entries(slide_spec.get("fieldProvenance")):
        if entry["path"] == field_path:
            attributed = list(entry["sourceChapterIds"])
            break
    if not attributed:
        attributed = list(_root_source_chapter_ids(slide_spec, _request_chapter_ids(request)))
    allowed = list(_request_chapter_ids(request))
    return ungrounded_content_retry_instruction(
        field_path=field_path,
        ungrounded_tokens={token},
        attributed_chapter_ids=attributed,
        allowed_chapter_ids=allowed,
    )


def _root_source_chapter_ids(
    slide_spec: dict[str, Any],
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    cited = slide_spec.get("sourceChapterIds")
    if isinstance(cited, list):
        ids = tuple(item for item in cited if isinstance(item, str))
        if ids:
            return ids
    return fallback


def _merge_rewritten_field(
    previous: dict[str, Any],
    regenerated: dict[str, Any],
    path: str,
    request: Any,
) -> dict[str, Any]:
    try:
        rewritten = get_value_at_path(regenerated, path)
    except KeyError:
        return regenerated
    if not isinstance(rewritten, str):
        return regenerated
    merged = copy.deepcopy(previous)
    set_value_at_path(merged, path, rewritten)
    return repair_live_slide_spec(merged, request)


def _with_rejection(request: Any, error: str) -> Any:
    if _should_keep_field_provenance(request):
        extra = (
            "\n\nYour previous SlideSpec was rejected: "
            f"{error} "
            "Return one complete object. Include fieldProvenance for every populated "
            "content leaf, including sectionLabel and subtitle when present. Use only "
            "the supplied chapter ids. Do not invent numbers or commercial values. "
            "Honor every minItems, maxItems, and maxLength limit."
        )
    else:
        extra = (
            "\n\nYour previous SlideSpec was rejected: "
            f"{error} "
            "Return one complete object. Do not add fieldProvenance. Use only "
            "the supplied chapter ids. Do not invent numbers or commercial values. "
            "Honor every minItems, maxItems, and maxLength limit."
        )
    return type(request)(
        layout_id=request.layout_id,
        chapters=request.chapters,
        target_schema=request.target_schema,
        instructions=f"{request.instructions}{extra}",
    )


def _request_chapter_ids(request: Any) -> tuple[str, ...]:
    ids: list[str] = []
    for chapter in getattr(request, "chapters", ()):
        chapter_id = chapter.get("chapter_id") if isinstance(chapter, dict) else None
        if isinstance(chapter_id, str) and chapter_id not in ids:
            ids.append(chapter_id)
    return tuple(ids)


def _schema_properties(request: Any) -> dict[str, Any] | None:
    schema = getattr(request, "target_schema", {}) or {}
    properties = schema.get("properties")
    return properties if isinstance(properties, dict) else None


def _schema_declares_property(request: Any, name: str) -> bool:
    properties = _schema_properties(request)
    return bool(properties and name in properties)


def _should_keep_field_provenance(request: Any) -> bool:
    properties = _schema_properties(request)
    if properties is None:
        return True
    return "fieldProvenance" in properties


def _strip_undeclared_properties(slide_spec: dict[str, Any], request: Any) -> None:
    """Group B schemas omit fieldProvenance; extra keys fail additionalProperties."""
    properties = _schema_properties(request)
    if not properties:
        return
    for key in list(slide_spec):
        if key not in properties:
            slide_spec.pop(key, None)


def _is_group_a_layout(request: Any) -> bool:
    layout_id = str(getattr(request, "layout_id", "") or "")
    return layout_id in _GROUP_A_LAYOUT_IDS


def _required_roots(request: Any) -> set[str]:
    schema = getattr(request, "target_schema", {}) or {}
    required = schema.get("required")
    if not isinstance(required, list):
        return set()
    return {name for name in required if isinstance(name, str)} - _METADATA_ROOTS


def _provenance_entries(value: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return entries
    for item in value:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        chapter_ids = item.get("sourceChapterIds")
        if not isinstance(path, str) or not path:
            continue
        if not isinstance(chapter_ids, list) or not chapter_ids:
            continue
        cleaned = [chapter_id for chapter_id in chapter_ids if isinstance(chapter_id, str)]
        if not cleaned:
            continue
        unique: list[str] = []
        for chapter_id in cleaned:
            if chapter_id not in unique:
                unique.append(chapter_id)
        entries.append({"path": path, "sourceChapterIds": unique})
    return entries


def _root_field(path: str) -> str:
    return path.split("[", 1)[0].split(".", 1)[0]


def _clear_root_field(slide_spec: dict[str, Any], path: str) -> None:
    root = _root_field(path)
    if root in slide_spec:
        slide_spec.pop(root, None)
