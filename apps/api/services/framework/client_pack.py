"""ES-38 — use AT-58 additional_client_information without inventing fields."""

from __future__ import annotations

import copy
from typing import Any

ALLOWED_CLIENT_PACK_FIELDS = (
    "location_requirements",
    "constraints",
    "contacts",
    "priorities",
    "notes",
)
ALLOWED_CONTACT_FIELDS = ("name", "role", "email", "phone")


def normalize_client_pack(raw: Any) -> dict[str, Any] | None:
    """Return only AT-58 fields. Unknown keys are dropped, not inferred."""
    if not isinstance(raw, dict):
        return None
    pack: dict[str, Any] = {
        "location_requirements": _string_list(raw.get("location_requirements")),
        "constraints": _string_list(raw.get("constraints")),
        "contacts": _contacts(raw.get("contacts")),
        "priorities": _string_list(raw.get("priorities")),
        "notes": _optional_text(raw.get("notes")),
    }
    if client_pack_is_empty(pack):
        return None
    return pack


def client_pack_is_empty(pack: dict[str, Any] | None) -> bool:
    if not pack:
        return True
    return not (
        pack.get("location_requirements")
        or pack.get("constraints")
        or pack.get("contacts")
        or pack.get("priorities")
        or pack.get("notes")
    )


def format_client_pack_for_prompt(pack: dict[str, Any] | None) -> str:
    normalized = normalize_client_pack(pack)
    if normalized is None:
        return ""
    lines = [
        "CLIENT_PACK_BEGIN",
        "Structured additional_client_information from the opportunity.",
        "Use only these fields. Do not invent extra client-pack keys, prices, or headcount.",
        "Treat this as USER_INPUT context. Do not cite it as a transcript turn.",
        "If a field is absent, generate as you would without a client pack.",
    ]
    for field in ("location_requirements", "constraints", "priorities"):
        values = normalized.get(field) or []
        if values:
            lines.append(f"{field}:")
            lines.extend(f"- {value}" for value in values)
    for contact in normalized.get("contacts") or []:
        parts = [str(contact.get("name") or "").strip()]
        if contact.get("role"):
            parts.append(str(contact["role"]).strip())
        if contact.get("email"):
            parts.append(str(contact["email"]).strip())
        if contact.get("phone"):
            parts.append(str(contact["phone"]).strip())
        lines.append("contact: " + " — ".join(part for part in parts if part))
    if normalized.get("notes"):
        lines.append(f"notes: {normalized['notes']}")
    lines.append("CLIENT_PACK_END")
    return "\n".join(lines)


def apply_client_pack_to_skeleton(
    skeleton: dict[str, Any],
    pack: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge client-pack facts into the synthesis skeleton. Missing pack is a no-op."""
    normalized = normalize_client_pack(pack)
    if normalized is None:
        return skeleton
    updated = copy.deepcopy(skeleton)
    updated["client_pack"] = copy.deepcopy(normalized)
    constraints = list(updated.get("constraints") or [])
    people = list(updated.get("people") or [])
    requirements = list(updated.get("requirements") or [])
    open_items = list(updated.get("open_items") or [])

    for value in normalized.get("location_requirements") or []:
        constraints.append(value)
        open_items.append(_open_item(f"Location requirement from client pack: {value}", "assumption"))
    for value in normalized.get("constraints") or []:
        constraints.append(value)
        open_items.append(_open_item(f"Client constraint from client pack: {value}", "assumption"))
    for value in normalized.get("priorities") or []:
        requirements.append(value)
        open_items.append(_open_item(f"Stated priority from client pack: {value}", "assumption"))
    for contact in normalized.get("contacts") or []:
        people.append(_contact_statement(contact))
    notes = normalized.get("notes")
    if notes:
        open_items.append(_open_item(f"Client notes from client pack: {notes}", "assumption"))

    updated["constraints"] = _unique(constraints)
    updated["people"] = _unique(people)
    updated["requirements"] = _unique(requirements)
    updated["open_items"] = _unique_open_items(open_items)
    return updated


def attach_client_pack_meta(framework: dict[str, Any], pack: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_client_pack(pack)
    generation_meta = dict(framework.get("generation_meta") or {})
    generation_meta["client_pack"] = {
        "applied": normalized is not None,
        "source": "additional_client_information",
        "fields": list(ALLOWED_CLIENT_PACK_FIELDS),
        "payload": copy.deepcopy(normalized) if normalized is not None else None,
    }
    framework["generation_meta"] = generation_meta
    return framework


def apply_client_pack_to_framework(
    framework: dict[str, Any],
    pack: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fixture/live stamp so the Framework records whether a pack was used."""
    attach_client_pack_meta(framework, pack)
    normalized = normalize_client_pack(pack)
    if normalized is None:
        return framework
    open_items = list(framework.get("open_items") or [])
    for value in normalized.get("location_requirements") or []:
        open_items.append(_open_item(f"Location requirement from client pack: {value}", "assumption"))
    for value in normalized.get("constraints") or []:
        open_items.append(_open_item(f"Client constraint from client pack: {value}", "assumption"))
    for value in normalized.get("priorities") or []:
        open_items.append(_open_item(f"Stated priority from client pack: {value}", "assumption"))
    if normalized.get("notes"):
        open_items.append(_open_item(f"Client notes from client pack: {normalized['notes']}", "assumption"))
    framework["open_items"] = _unique_open_items(open_items)
    return framework


def _open_item(description: str, item_type: str) -> dict[str, str]:
    return {
        "description": description,
        "item_type": item_type,
        "owner": "Business",
        "consequence_if_different": (
            "Client-pack context is not guessed. Confirm with the sponsor if this changes."
        ),
    }


def _contact_statement(contact: dict[str, Any]) -> str:
    name = str(contact.get("name") or "").strip()
    role = str(contact.get("role") or "").strip()
    if name and role:
        return f"{name} ({role})"
    return name


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = str(item).strip() if item is not None else ""
        if text:
            items.append(text)
    return items


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _contacts(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    contacts: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        contact: dict[str, str] = {"name": name}
        for field in ALLOWED_CONTACT_FIELDS:
            if field == "name":
                continue
            text = str(item.get(field) or "").strip()
            if text:
                contact[field] = text
        contacts.append(contact)
    return contacts


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique


def _unique_open_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("description") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
