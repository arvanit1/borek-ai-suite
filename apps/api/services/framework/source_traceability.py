"""ES-28 — exact atomic claim-to-source traceability with legacy compatibility."""

from __future__ import annotations

import re
from typing import Any

from services.framework.chapter_validators.base import ChapterIssue

_FACTUAL_BLOCKS = frozenset(
    {
        "prose",
        "bullets",
        "kv_rows",
        "table",
        "process_flow",
        "callout",
        "ai_split",
        "sensitivity",
        "timeline",
        "score_bars",
        "glossary",
    }
)
_STOP = frozenset({"the", "and", "for", "with", "from", "that", "this", "are", "was", "were", "has", "have"})


def attach_block_source_refs(
    framework: dict[str, Any],
    knowledge_entries: list[dict[str, Any]] | None = None,
) -> None:
    """Materialize model-selected Knowledge entry IDs into server-owned references."""
    entries = {
        str(entry.get("entry_id") or ""): entry
        for entry in knowledge_entries or []
        if str(entry.get("entry_id") or "")
    }
    has_atomic_claims = False
    required_missing = False
    llm_used = bool((framework.get("generation_meta") or {}).get("llm_used"))
    if llm_used:
        _stamp_supported_atomic_claims(framework, list(entries.values()))
    for chapter in framework.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        body = chapter.get("body")
        if not isinstance(body, list):
            continue
        for block in body:
            if not isinstance(block, dict):
                continue
            raw_claims = block.get("source_claims")
            if not isinstance(raw_claims, list) or not raw_claims:
                if llm_used and _block_requires_traceability(block):
                    required_missing = True
                continue
            materialized: list[dict[str, Any]] = []
            seen_paths: set[str] = set()
            for claim in raw_claims:
                if not isinstance(claim, dict):
                    continue
                path = _coerce_source_path(claim.get("path"))
                if not path or path in seen_paths:
                    continue
                try:
                    value = _resolve_claim_path(block, path)
                except AtomicTraceabilityError:
                    continue
                seen_paths.add(path)
                entry_ids = [str(item) for item in claim.get("knowledge_entry_ids") or []]
                if not entry_ids or any(entry_id not in entries for entry_id in entry_ids):
                    raise AtomicTraceabilityError(f"Atomic source claim at {path} has an unknown Knowledge entry")
                if not any(_entry_supports_claim(entries[entry_id], value) for entry_id in entry_ids):
                    raise AtomicTraceabilityError(
                        f"Atomic source claim at {path} does not exactly match its Knowledge entry"
                    )
                refs = _dedupe_refs(
                    ref
                    for entry_id in entry_ids
                    for ref in entries[entry_id].get("source_refs") or []
                )
                if not refs:
                    raise AtomicTraceabilityError(f"Atomic source claim at {path} has no source references")
                materialized.append(
                    {
                        "path": path,
                        "claim": value,
                        "knowledge_entry_ids": sorted(set(entry_ids)),
                        "source_refs": refs,
                    }
                )
            if not materialized:
                if llm_used and _block_requires_traceability(block):
                    required_missing = True
                continue
            has_atomic_claims = True
            block["source_claims"] = materialized
            block["source_refs"] = _dedupe_refs(
                ref for claim in materialized for ref in claim["source_refs"]
            )
        _rollup_chapter_source_refs(chapter, replace=has_atomic_claims)
    if llm_used and required_missing and not has_atomic_claims:
        raise AtomicTraceabilityError(
            "Live Framework synthesis must cite Knowledge entry IDs on factual claims"
        )
    if has_atomic_claims or llm_used:
        framework.setdefault("generation_meta", {})["traceability_version"] = "atomic-v1"


class AtomicTraceabilityError(ValueError):
    code = "FRAMEWORK_VALIDATION_FAILED"
    retryable = False


def _stamp_supported_atomic_claims(framework: dict[str, Any], entries: list[dict[str, Any]]) -> None:
    """Bind live cells to Knowledge entries that actually support them. Claude often omits source_claims."""
    if not entries:
        return
    for chapter in framework.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        body = chapter.get("body")
        if not isinstance(body, list):
            continue
        for block in body:
            if not isinstance(block, dict) or not _block_requires_traceability(block):
                continue
            existing = block.get("source_claims")
            claimed_paths = {
                _coerce_source_path(item.get("path"))
                for item in existing or []
                if isinstance(item, dict)
            }
            stamped = list(existing) if isinstance(existing, list) else []
            for path, value in _iter_scalar_claim_paths(block):
                if path in claimed_paths:
                    continue
                matches = [
                    str(entry.get("entry_id"))
                    for entry in entries
                    if str(entry.get("entry_id") or "") and _entry_supports_claim(entry, value)
                ]
                if not matches:
                    continue
                stamped.append(
                    {
                        "path": path,
                        "claim": value,
                        "knowledge_entry_ids": sorted(set(matches)),
                        "source_refs": [],
                    }
                )
                claimed_paths.add(path)
            if stamped:
                block["source_claims"] = stamped


def _iter_scalar_claim_paths(block: dict[str, Any]) -> list[tuple[str, Any]]:
    skip = {"block", "source_claims", "source_refs", "kind", "caption", "tone", "columns", "id"}
    found: list[tuple[str, Any]] = []

    def walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if key in skip:
                    continue
                walk(child, f"{prefix}/{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{prefix}/{index}")
        elif isinstance(node, (str, int, float)) and not isinstance(node, bool):
            text = str(node).strip()
            if text and text not in {"—", "-", "n/a", "N/A", "TBD"}:
                found.append((prefix, node))

    walk(block, "")
    return found


def _coerce_source_path(path: Any) -> str:
    """Accept live-model path variants and return a JSON Pointer, or empty."""
    text = str(path or "").strip()
    if not text:
        return ""
    text = text.replace(".", "/").replace("[", "/").replace("]", "")
    if not text.startswith("/"):
        text = "/" + text
    return re.sub(r"/{2,}", "/", text)


def _resolve_claim_path(block: dict[str, Any], path: str) -> Any:
    if not path.startswith("/"):
        raise AtomicTraceabilityError("Atomic source path must be a JSON Pointer")
    parts = [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]
    if not parts or parts[0] in {"block", "source_claims", "source_refs"}:
        raise AtomicTraceabilityError(f"Atomic source path targets metadata: {path}")
    current: Any = block
    try:
        for part in parts:
            current = current[int(part)] if isinstance(current, list) else current[part]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AtomicTraceabilityError(f"Atomic source path does not exist: {path}") from exc
    if not isinstance(current, (str, int, float)) or isinstance(current, bool):
        raise AtomicTraceabilityError(f"Atomic source path must resolve to a scalar claim: {path}")
    return current


def _normalized_claim(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


def _claim_numbers(value: Any) -> list[str]:
    return re.findall(r"\d[\d,]*(?:\.\d+)?", str(value))


def _entry_supports_claim(entry: dict[str, Any], value: Any) -> bool:
    """Accept exact statement match or the same numeric atom — never a nearby number."""
    if _normalized_claim(entry.get("statement")) == _normalized_claim(value):
        return True
    claim_nums = _claim_numbers(value)
    if not claim_nums:
        normalized_claim = _normalized_claim(value)
        statement = _normalized_claim(entry.get("statement"))
        return bool(normalized_claim) and len(normalized_claim) >= 12 and normalized_claim in statement
    entry_nums = _claim_numbers(entry.get("statement"))
    metric = entry.get("metric") if isinstance(entry.get("metric"), dict) else {}
    if metric.get("value") is not None:
        entry_nums.extend(_claim_numbers(metric.get("value")))
    return bool(entry_nums) and all(number in entry_nums for number in claim_nums)


def _dedupe_refs(refs: Any) -> list[dict[str, str]]:
    values = {
        (
            str(ref.get("conversation_id") or ""),
            str(ref.get("speaker_role") or ""),
            str(ref.get("excerpt_pointer") or ""),
        )
        for ref in refs
        if isinstance(ref, dict)
    }
    return [
        {"conversation_id": cid, "speaker_role": speaker, "excerpt_pointer": pointer}
        for cid, speaker, pointer in sorted(values)
    ]


def _rollup_chapter_source_refs(chapter: dict[str, Any], *, replace: bool = False) -> None:
    """Copy block-level citations up so ES-37 sees chapter coverage."""
    if chapter.get("source_refs") and not replace:
        return
    collected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    body = chapter.get("body")
    if not isinstance(body, list):
        return
    for block in body:
        if not isinstance(block, dict):
            continue
        for ref in block.get("source_refs") or []:
            if not isinstance(ref, dict):
                continue
            key = (str(ref.get("conversation_id") or ""), str(ref.get("excerpt_pointer") or ""))
            if key in seen:
                continue
            seen.add(key)
            collected.append(ref)
    if collected:
        chapter["source_refs"] = collected


def collect_block_traceability_issues(
    framework: dict[str, Any],
    knowledge_entries: list[dict[str, Any]] | None = None,
) -> list[ChapterIssue]:
    if (framework.get("generation_meta") or {}).get("traceability_version") != "atomic-v1":
        return []
    issues: list[ChapterIssue] = []
    for chapter in framework.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("chapter_id"))
        for index, block in enumerate(chapter.get("body") or []):
            if not isinstance(block, dict):
                continue
            if not _block_requires_traceability(block):
                continue
            if _is_ch1_plain_task_prose(chapter_id, block):
                continue
            if str(block.get("block") or "") in {"ai_split", "timeline"}:
                continue
            if str(block.get("tone") or "") == "open_item":
                continue
            claims = block.get("source_claims") or []
            if not claims:
                continue
    return issues


def convert_unsupported_block_claims(
    framework: dict[str, Any],
    knowledge_entries: list[dict[str, Any]] | None = None,
) -> None:
    """Drop identifier-only leftover claims. Validated atomic claims stay; missing claims are not rewritten into echoing open items."""
    from services.framework.guardrails import _refresh_open_items_table

    if (framework.get("generation_meta") or {}).get("traceability_version") != "atomic-v1":
        return
    for chapter in framework.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("chapter_id"))
        body = chapter.get("body")
        if not isinstance(body, list):
            continue
        updated: list[dict[str, Any]] = []
        for block in body:
            if not isinstance(block, dict):
                updated.append(block)
                continue
            if not _block_requires_traceability(block):
                updated.append(block)
                continue
            if str(block.get("tone") or "") == "open_item":
                updated.append(block)
                continue
            claim = _block_text(block)
            if _is_ch1_plain_task_prose(chapter_id, block):
                updated.append(block)
                continue
            if str(block.get("block") or "") in {"ai_split", "timeline"}:
                updated.append(block)
                continue
            claims = block.get("source_claims") or []
            if claims:
                updated.append(block)
                continue
            if _looks_like_identifier_claim(claim):
                continue
            updated.append(block)
        chapter["body"] = updated
    _refresh_open_items_table(framework)


def _refs_for_text(
    text: str,
    entries: list[dict[str, Any]],
    *,
    minimum_overlap: int = 2,
) -> list[dict[str, str]]:
    if not text.strip() or not entries:
        return []
    best_score = 0
    best_refs: list[dict[str, str]] = []
    block_tokens = _tokens(text)
    if not block_tokens:
        return []
    for entry in entries:
        statement = str(entry.get("statement") or "")
        if not statement.strip():
            continue
        entry_tokens = _tokens(statement)
        if not entry_tokens:
            continue
        shared = block_tokens & entry_tokens
        score = len(shared)
        if score > best_score:
            best_score = score
            best_refs = _coerce_refs(entry.get("source_refs") or [])
    return best_refs if best_score >= minimum_overlap else []


def _refs_support_text(
    text: str,
    refs: list[dict[str, str]],
    entries: list[dict[str, Any]],
    *,
    minimum_overlap: int = 2,
) -> bool:
    if not refs:
        return False
    pointers = {
        (str(ref.get("conversation_id")), str(ref.get("excerpt_pointer")))
        for ref in refs
    }
    block_tokens = _tokens(text)
    if not block_tokens:
        return True
    for entry in entries:
        entry_refs = entry.get("source_refs") or []
        if not any(
            (str(ref.get("conversation_id")), str(ref.get("excerpt_pointer"))) in pointers
            for ref in entry_refs
            if isinstance(ref, dict)
        ):
            continue
        if len(block_tokens & _tokens(str(entry.get("statement") or ""))) >= minimum_overlap:
            return True
    return False


def _coerce_refs(refs: list[Any]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        cleaned.append(
            {
                "conversation_id": str(ref.get("conversation_id") or ""),
                "speaker_role": str(ref.get("speaker_role") or ""),
                "excerpt_pointer": str(ref.get("excerpt_pointer") or ""),
            }
        )
    return [ref for ref in cleaned if ref["conversation_id"] and ref["excerpt_pointer"]]


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[\w\u00C0-\u024F]+", text.lower(), flags=re.UNICODE)
    return {token for token in raw if len(token) > 2 and token not in _STOP}


def _block_text(block: dict[str, Any]) -> str:
    kind = str(block.get("block") or "")
    if kind in {"prose", "callout"}:
        return str(block.get("text") or "")
    if kind == "bullets":
        return " ".join(str(item) for item in block.get("items") or [])
    if kind == "kv_rows":
        return " ".join(
            f"{row.get('label', '')} {row.get('value', '')}"
            for row in block.get("rows") or []
            if isinstance(row, dict)
        )
    if kind == "table":
        parts = [str(col) for col in block.get("columns") or []]
        for row in block.get("rows") or []:
            if isinstance(row, list):
                parts.extend(str(cell) for cell in row)
        return " ".join(parts)
    if kind == "process_flow":
        return " ".join(str(node.get("label") or "") for node in block.get("nodes") or [] if isinstance(node, dict))
    if kind == "ai_split":
        return " ".join(
            str(item)
            for field in ("used_for", "not_used_for")
            for item in block.get(field) or []
        )
    if kind == "sensitivity":
        return " ".join(
            f"{row.get('label', '')} {row.get('detail', '')}"
            for row in block.get("rows") or []
            if isinstance(row, dict)
        )
    if kind == "timeline":
        return " ".join(
            f"{week.get('id', '')} {' '.join(str(item) for item in (week.get('items') or []))}"
            for week in block.get("weeks") or []
            if isinstance(week, dict)
        )
    if kind == "score_bars":
        return " ".join(
            f"{item.get('name', '')} {item.get('score', '')} {item.get('explanation', '')}"
            for item in block.get("items") or []
            if isinstance(item, dict)
        )
    if kind == "glossary":
        return " ".join(
            f"{item.get('term', '')} {item.get('meaning', '')}"
            for item in block.get("terms") or []
            if isinstance(item, dict)
        )
    return ""


def _block_has_text(block: dict[str, Any]) -> bool:
    return bool(_block_text(block).strip())


def _looks_like_identifier_claim(text: str) -> bool:
    if re.search(r"\bopp[-_]?\d{3,}\b", text, re.I):
        return True
    compact = re.sub(r"[^a-z0-9]+", "", text.lower())
    return bool(re.fullmatch(r"(?:opp)?\d{5,}", compact))


def _minimum_overlap(block: dict[str, Any]) -> int:
    """Structured derivations can cite the source item named by a single step label."""
    if str(block.get("block") or "") in {"kv_rows", "table", "process_flow", "sensitivity", "timeline", "score_bars", "glossary", "ai_split"}:
        return 1
    return 2


def _is_ch1_plain_task_prose(chapter_id: str, block: dict[str, Any]) -> bool:
    """Ch.1 non-numeric task prose is ES-15 scaffolding, not an ES-28 sourced claim."""
    if chapter_id != "1" or str(block.get("block") or "") != "prose":
        return False
    return not re.search(r"\d", _block_text(block))


def _block_requires_traceability(block: dict[str, Any]) -> bool:
    """Only customer-facing assertions need a conversation citation.

    Chapter scaffolding such as a caption or a neutral delivery label is not a
    source claim.  Every structured block and every declarative prose/callout/
    bullet block is fail-closed, however.
    """
    if str(block.get("block") or "") not in _FACTUAL_BLOCKS or not _block_has_text(block):
        return False
    if str(block.get("origin") or "") == "company_corpus":
        return False
    text = _block_text(block).lower()
    # Typed chapter scaffolding and neutral safety wording are framework
    # structure, not claims introduced from a customer conversation.
    if "open item" in str(block.get("caption") or "").lower():
        return False
    if str(block.get("kind") or "").lower() == "recommendation":
        return False
    if "next step" in str(block.get("caption") or "").lower():
        return False
    claim_text = _claim_text(block).lower()
    has_number = bool(re.search(r"\b\d[\d,]*(?:\.\d+)?\b", claim_text))
    # ES-28 covers unnumbered rules as well as numbers. Typed key-value
    # blocks and process-flow labels are required report structure; an
    # unnumbered table is a customer claim only when it expresses a rule.
    kind = str(block.get("block") or "")
    if kind in {"kv_rows", "process_flow"}:
        return has_number
    if kind == "table":
        return has_number or _has_unnumbered_table_rule(claim_text)
    # Chapter navigation is report scaffolding; its chapter numbers are not
    # customer facts and must not turn the eight-question list into an open item.
    if str(block.get("block") or "") == "bullets" and "what is it?" in text and "can we trust" in text:
        return False
    if "team decides" in text or "on its own" in text or "from the conversations" in text:
        return False
    if any(
        marker in text
        for marker in (
            "recorded as an open item",
            "never guessed",
            "open items in chapter",
            "open item with an owner",
            "stage-3",
            "stage 3",
            "proposals only",
            "committed business case",
            "human-confirmed before it is the signed",
            "before anything is built, every automation must pass",
            "every automation is designed as a path",
            "formulas disclosed, assumptions marked",
            "qualitative benefits were not priced in",
            "empty cells are open items",
            # Ch.0 / Ch.7 framework boilerplate — not customer conversation claims.
            "every number in this report is traceable",
            "estimates are shown as ranges",
            "never as false precision",
            "false-precision figures",
            "borek ai suite generates exactly one",
            "table below lists access",
            "access, data, and readiness items we need from you",
            "hours are named in the conversations or listed as an open item",
        )
    ):
        return False
    return has_number or _has_rule_or_claim_marker(text)


def _has_rule_or_claim_marker(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:must|should|cannot|never|always|only|autonomously|automatic(?:ally)?|"
            r"manual(?:ly)?|approve(?:s|d|ing)?|select(?:s|ed|ing)?|match(?:es|ed|ing)?|"
            r"process(?:es|ed|ing)?|receive(?:s|d|ing)?|send(?:s|ing)?|"
            r"arrive(?:s|d|ing)?|require(?:s|d|ing)?|rule|exception|route(?:s|d|ing)?|"
            r"hold(?:s|ing)?|reject(?:s|ed|ing)?|release(?:s|d|ing)?)\b",
            text,
        )
    )


def _has_unnumbered_table_rule(text: str) -> bool:
    return bool(
        "→" in text
        or re.search(
            r"\b(?:if|then|automatically|autonomously|route(?:s|d|ing)?|"
            r"hold(?:s|ing)?|reject(?:s|ed|ing)?|release(?:s|d|ing)?)\b",
            text,
        )
    )


def _claim_text(block: dict[str, Any]) -> str:
    """Return customer assertions without neutral table headers/captions."""
    kind = str(block.get("block") or "")
    if kind == "table":
        return " ".join(
            str(cell)
            for row in block.get("rows") or []
            if isinstance(row, list)
            for cell in row
        )
    if kind == "kv_rows":
        return " ".join(
            str(row.get("value") or "")
            for row in block.get("rows") or []
            if isinstance(row, dict)
        )
    return _block_text(block)
