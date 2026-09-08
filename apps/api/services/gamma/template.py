"""JJ-26: the Borek Gamma template contract.

`packages/contracts/gamma_template.json` is the single source of truth for the
template id, its named content slots, and which Framework chapter feeds each
slot. Branding lives in the Gamma template itself and is never part of a
request, so nothing here describes colours, fonts, or masters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[4] / "packages" / "contracts" / "gamma_template.json"
)


class GammaTemplateContractError(RuntimeError):
    """The template contract on disk is unusable."""


@dataclass(frozen=True)
class GammaSlotDefinition:
    name: str
    label: str
    layout_id: str
    source: str
    source_chapter_ids: tuple[str, ...]
    required: bool
    max_chars: int
    classification: str

    @property
    def is_chapter_fed(self) -> bool:
        return self.source == "framework_chapters"


@dataclass(frozen=True)
class GammaCardDefinition:
    card: int
    layout_id: str
    title: str
    slots: tuple[str, ...]


@dataclass(frozen=True)
class GammaLogoRules:
    slot: str
    cards: tuple[str, ...]
    position: str
    max_height_pct: float
    min_clear_space_pct: float
    co_brand_with_borek_logo: bool
    min_edge_px: int
    min_placement_area_px: int
    max_aspect_ratio: float
    opaque_formats: tuple[str, ...]
    fallbacks: dict[str, str]
    signed_url_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class GammaTemplate:
    template_id: str
    template_version: str
    branding_locked: bool
    locked_keys: frozenset[str]
    cards: tuple[GammaCardDefinition, ...]
    slots: tuple[GammaSlotDefinition, ...]
    client_logo: GammaLogoRules

    @property
    def slot_names(self) -> tuple[str, ...]:
        return tuple(slot.name for slot in self.slots)

    def slot(self, name: str) -> GammaSlotDefinition:
        for definition in self.slots:
            if definition.name == name:
                return definition
        raise GammaTemplateContractError(f"'{name}' is not a named slot of the Borek template.")


@lru_cache(maxsize=1)
def load_gamma_template() -> GammaTemplate:
    try:
        raw = json.loads(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GammaTemplateContractError(f"Cannot read {_TEMPLATE_PATH}: {exc}") from exc
    return _parse_template(raw)


def reset_gamma_template_cache() -> None:
    load_gamma_template.cache_clear()


def _parse_template(raw: dict[str, Any]) -> GammaTemplate:
    branding = raw.get("branding") or {}
    slots = tuple(_parse_slot(item) for item in raw.get("slots") or ())
    if not slots:
        raise GammaTemplateContractError("The Borek template defines no content slots.")
    cards = tuple(
        GammaCardDefinition(
            card=int(item["card"]),
            layout_id=str(item["layout_id"]),
            title=str(item["title"]),
            slots=tuple(str(name) for name in item.get("slots") or ()),
        )
        for item in raw.get("cards") or ()
    )
    declared = {slot.name for slot in slots}
    for card in cards:
        unknown = [name for name in card.slots if name not in declared]
        if unknown:
            raise GammaTemplateContractError(
                f"Card {card.card} references undeclared slots: {unknown}."
            )
    return GammaTemplate(
        template_id=str(raw["template_id"]),
        template_version=str(raw["template_version"]),
        branding_locked=bool(branding.get("locked", True)),
        locked_keys=frozenset(str(key) for key in branding.get("locked_keys") or ()),
        cards=cards,
        slots=slots,
        client_logo=_parse_logo_rules(raw.get("client_logo") or {}),
    )


def _parse_slot(item: dict[str, Any]) -> GammaSlotDefinition:
    try:
        return GammaSlotDefinition(
            name=str(item["name"]),
            label=str(item["label"]),
            layout_id=str(item["layout_id"]),
            source=str(item["source"]),
            source_chapter_ids=tuple(str(value) for value in item.get("source_chapter_ids") or ()),
            required=bool(item["required"]),
            max_chars=int(item["max_chars"]),
            classification=str(item["classification"]),
        )
    except KeyError as exc:
        raise GammaTemplateContractError(f"Slot definition is missing {exc}.") from exc


def _parse_logo_rules(raw: dict[str, Any]) -> GammaLogoRules:
    gate = raw.get("quality_gate") or {}
    return GammaLogoRules(
        slot=str(raw.get("slot") or "cover.client_logo"),
        cards=tuple(str(value) for value in raw.get("cards") or ()),
        position=str(raw.get("position") or "bottom_right"),
        max_height_pct=float(raw.get("max_height_pct") or 6.0),
        min_clear_space_pct=float(raw.get("min_clear_space_pct") or 3.0),
        co_brand_with_borek_logo=bool(raw.get("co_brand_with_borek_logo", True)),
        min_edge_px=int(gate.get("min_edge_px") or 128),
        min_placement_area_px=int(gate.get("min_placement_area_px") or 0),
        max_aspect_ratio=float(gate.get("max_aspect_ratio") or 8.0),
        opaque_formats=tuple(str(value) for value in gate.get("opaque_formats") or ()),
        fallbacks={str(key): str(value) for key, value in (raw.get("fallbacks") or {}).items()},
        signed_url_prefixes=tuple(str(value) for value in raw.get("signed_url_prefixes") or ()),
    )
