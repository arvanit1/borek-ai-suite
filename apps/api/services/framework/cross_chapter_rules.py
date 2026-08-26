"""ES-28 no invented facts; ES-29 one opportunity / process per object."""

from __future__ import annotations

import re
from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, ChapterValidationError
from services.framework.source_traceability import collect_block_traceability_issues

_PROCESS_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("accounts_payable_3way", ("3-way", "three-way", "invoice match", "accounts payable", "invoice processing")),
    ("warehouse_delivery", ("delivery note match", "delivery-note match", "outbound shipment match", "warehouse match")),
    ("purchase_requisition", ("purchase requisition", "requisition approval", "procurement request")),
    ("payroll", ("payroll processing", "salary run")),
    ("onboarding", ("employee onboarding", "new hire onboarding")),
    ("quality_check", ("incoming quality", "quality inspection")),
    ("expense_report", ("expense report", "expense reports", "concur expense")),
    ("refund_request", ("refund request", "refund requests", "refund handling", "refund approval")),
    ("password_reset", ("password reset", "password resets", "reset password")),
    ("contract_intake", ("contract intake", "contract triage", "contract review")),
    ("vendor_onboarding", ("vendor onboarding", "supplier onboarding", "onboard vendors")),
    ("supplier_inquiry", ("supplier inquiry", "supplier enquiries", "vendor inquiry")),
    ("accounts_receivable_dunning", ("dunning email", "collections email", "payment reminder")),
    ("service_ticket", ("service ticket", "support ticket", "helpdesk ticket", "incident ticket")),
)


class MultiProcessError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


def flag_multi_process(
    knowledge_models: list[dict[str, Any]],
    opportunity_id: str,
    *,
    include_heuristics: bool = True,
) -> None:
    """ES-29 pre-check; production scope is decided by the semantic Claude gate."""
    opp_ids = {str(model.get("opportunity_id")) for model in knowledge_models if model.get("opportunity_id")}
    if opportunity_id:
        opp_ids.add(str(opportunity_id))
    named = {item for item in opp_ids if item and item != "None"}
    if len(named) > 1:
        raise MultiProcessError(
            "This transcript set covers more than one process. It is flagged and not merged into one framework object."
        )
    if not include_heuristics:
        return
    for model in knowledge_models:
        processes = _distinct_processes(model)
        if len(processes) > 1:
            joined = ", ".join(sorted(processes))
            raise MultiProcessError(
                f"This conversation describes more than one process ({joined}). "
                "It is flagged and not merged into one framework object."
            )


def enforce_cross_chapter_rules(framework: dict[str, Any], knowledge_entries: list[dict[str, Any]]) -> None:
    issues: list[ChapterIssue] = []
    opportunity_ids = {framework.get("opportunity_id")}
    for ref in framework.get("generated_from") or []:
        if isinstance(ref, dict) and ref.get("opportunity_id"):
            opportunity_ids.add(ref["opportunity_id"])
    if len({item for item in opportunity_ids if item}) != 1:
        issues.append(
            ChapterIssue("all", "one_opportunity", "A FrameworkObject may cover exactly one opportunity (ES-29).")
        )

    issues.extend(collect_block_traceability_issues(framework, knowledge_entries))

    claimed_refs = []
    for chapter in framework.get("chapters") or []:
        for block in chapter.get("body") or []:
            if isinstance(block, dict):
                claimed_refs.extend(block.get("source_refs") or [])
        claimed_refs.extend(chapter.get("source_refs") or [])

    known_pointers = {
        (str(ref.get("conversation_id")), str(ref.get("excerpt_pointer")))
        for entry in knowledge_entries
        for ref in entry.get("source_refs") or []
    }
    if known_pointers:
        for ref in claimed_refs:
            pointer = (str(ref.get("conversation_id")), str(ref.get("excerpt_pointer")))
            if pointer not in known_pointers:
                issues.append(
                    ChapterIssue(
                        "all",
                        "unknown_citation",
                        f"Citation {pointer} is not in the knowledge model.",
                        hard=False,
                    )
                )

    hard = [issue for issue in issues if issue.hard]
    if hard:
        raise ChapterValidationError(issues)


def _distinct_processes(model: dict[str, Any]) -> set[str]:
    parts: list[str] = []
    for bucket in ("facts", "stated_requirements", "named_rules", "named_exceptions"):
        for entry in model.get(bucket) or []:
            if isinstance(entry, dict):
                parts.append(str(entry.get("statement") or ""))
    blob = " ".join(parts).lower()
    families: set[str] = set()
    for family, needles in _PROCESS_FAMILIES:
        if any(needle in blob for needle in needles):
            families.add(family)
    heads = _document_process_heads(blob)
    if not families:
        return heads
    extras = {head for head in heads if not _head_covered_by_families(head, families)}
    return families | extras


def _head_covered_by_families(head: str, families: set[str]) -> bool:
    if "accounts_payable_3way" in families and any(token in head for token in ("invoice", "goods receipt", "3-way")):
        return True
    if "warehouse_delivery" in families and "delivery" in head:
        return True
    if "purchase_requisition" in families and "requisition" in head:
        return True
    if "payroll" in families and "payroll" in head:
        return True
    return False


def _document_process_heads(blob: str) -> set[str]:
    """Catch distinct automation targets outside the fixed family list (ES-29)."""
    heads: set[str] = set()
    patterns = (
        r"\b(\d[\d,]*)\s+(invoices?|delivery notes?|requisitions?|payroll runs?|tickets?|claims?|refunds?|contracts?|password resets?)\b",
        r"\b(match(?:ing)?\s+(invoices?|delivery notes?|requisitions?|payroll|tickets?))\b",
        r"\b(process(?:ing)?\s+(invoices?|delivery notes?|requisitions?|payroll|tickets?|claims?|refunds?|contracts?))\b",
        r"\b(handle|handles|handling|approve|approves|approving|review|reviews|reviewing|triage|triages|triaging|reset|resets|resetting|onboard|onboards|onboarding)\s+(?:all\s+)?(invoices?|delivery notes?|requisitions?|payroll runs?|tickets?|claims?|refund requests?|refunds?|contracts?|password resets?|expense reports?)\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, blob, re.I):
            token = match.group(2 if match.lastindex and match.lastindex >= 2 else 1).lower().strip()
            if token:
                heads.add(token)
    return heads


def _looks_factual(body: Any) -> bool:
    if isinstance(body, str):
        return bool(body.strip())
    if isinstance(body, list):
        return any(_looks_factual(item) for item in body)
    if isinstance(body, dict):
        block = body.get("block")
        return block in {"prose", "kv_rows", "table", "process_flow", "callout"}
    return False
