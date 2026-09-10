"""JJ-26 / JJ-31: the Borek Gamma template contract.

`packages/contracts/gamma_template.json` is the single source of truth for the
template id, its named content slots, which Framework chapter feeds each slot,
and the `stage_profiles` that select cards, logo, and pricing per journey
stage. Branding lives in the Gamma template itself and is never part of a
request, so nothing here describes colours, fonts, or masters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
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
class GammaSlotOverride:
    source_chapter_ids: tuple[str, ...] | None = None
    max_chars: int | None = None


@dataclass(frozen=True)
class GammaStageProfile:
    stage: str
    label: str
    template_id: str
    cards: tuple[str, ...]
    pricing_permitted: bool
    client_logo: bool
    fact_kinds: frozenset[str]
    slot_overrides: dict[str, GammaSlotOverride]


@dataclass(frozen=True)
class GammaTemplate:
    template_id: str
    template_version: str
    branding_locked: bool
    locked_keys: frozenset[str]
    cards: tuple[GammaCardDefinition, ...]
    slots: tuple[GammaSlotDefinition, ...]
    client_logo: GammaLogoRules
    stage_profiles: dict[str, GammaStageProfile]

    @property
    def slot_names(self) -> tuple[str, ...]:
        return tuple(slot.name for slot in self.slots)

    def slot(self, name: str) -> GammaSlotDefinition:
        for definition in self.slots:
            if definition.name == name:
                return definition
        raise GammaTemplateContractError(f"'{name}' is not a named slot of the Borek template.")

    def profile(self, stage: str) -> GammaStageProfile:
        profile = self.stage_profiles.get(stage)
        if profile is None:
            raise GammaTemplateContractError(f"No stage profile named '{stage}'.")
        return profile

    def slots_for_stage(self, stage: str) -> tuple[GammaSlotDefinition, ...]:
        """Named slots enabled by the stage profile, in card order. Excluded cards emit nothing."""
        profile = self.profile(stage)
        included_names: list[str] = []
        seen: set[str] = set()
        allowed_cards = set(profile.cards)
        for card in self.cards:
            if card.layout_id not in allowed_cards:
                continue
            for name in card.slots:
                if name in seen:
                    continue
                seen.add(name)
                included_names.append(name)
        return tuple(self._apply_slot_override(self.slot(name), profile) for name in included_names)

    def _apply_slot_override(
        self,
        definition: GammaSlotDefinition,
        profile: GammaStageProfile,
    ) -> GammaSlotDefinition:
        override = profile.slot_overrides.get(definition.name)
        if override is None:
            return definition
        updates: dict[str, Any] = {}
        if override.source_chapter_ids is not None:
            updates["source_chapter_ids"] = override.source_chapter_ids
        if override.max_chars is not None:
            updates["max_chars"] = override.max_chars
        return replace(definition, **updates) if updates else definition


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
    layout_ids = {card.layout_id for card in cards}
    profiles = _parse_stage_profiles(raw.get("stage_profiles") or {}, layout_ids, declared)
    return GammaTemplate(
        template_id=str(raw["template_id"]),
        template_version=str(raw["template_version"]),
        branding_locked=bool(branding.get("locked", True)),
        locked_keys=frozenset(str(key) for key in branding.get("locked_keys") or ()),
        cards=cards,
        slots=slots,
        client_logo=_parse_logo_rules(raw.get("client_logo") or {}),
        stage_profiles=profiles,
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


_REQUIRED_STAGE_PROFILES = ("first_contact", "deepening", "concretisation")
_KNOWN_FACT_KINDS = frozenset({"service", "reference", "staffing", "pricing"})


def _parse_stage_profiles(
    raw: dict[str, Any],
    layout_ids: set[str],
    declared_slots: set[str],
) -> dict[str, GammaStageProfile]:
    if not raw:
        raise GammaTemplateContractError("The Borek template defines no stage_profiles.")
    missing = [stage for stage in _REQUIRED_STAGE_PROFILES if stage not in raw]
    if missing:
        raise GammaTemplateContractError(
            f"stage_profiles is missing required stages: {missing}."
        )
    profiles: dict[str, GammaStageProfile] = {}
    for stage, item in raw.items():
        if not isinstance(item, dict):
            raise GammaTemplateContractError(f"stage_profiles.{stage} must be an object.")
        cards = tuple(str(value) for value in item.get("cards") or ())
        unknown_cards = [layout_id for layout_id in cards if layout_id not in layout_ids]
        if unknown_cards:
            raise GammaTemplateContractError(
                f"stage_profiles.{stage} references unknown cards: {unknown_cards}."
            )
        if not cards:
            raise GammaTemplateContractError(f"stage_profiles.{stage} declares no cards.")
        fact_kinds = frozenset(str(value) for value in item.get("fact_kinds") or ())
        unknown_kinds = fact_kinds - _KNOWN_FACT_KINDS
        if unknown_kinds:
            raise GammaTemplateContractError(
                f"stage_profiles.{stage} has unknown fact_kinds: {sorted(unknown_kinds)}."
            )
        pricing_permitted = bool(item.get("pricing_permitted"))
        if pricing_permitted and "pricing" not in fact_kinds:
            raise GammaTemplateContractError(
                f"stage_profiles.{stage} permits pricing but does not list the pricing fact kind."
            )
        if not pricing_permitted and "pricing" in fact_kinds:
            raise GammaTemplateContractError(
                f"stage_profiles.{stage} lists pricing facts while pricing_permitted is false."
            )
        overrides = _parse_slot_overrides(item.get("slot_overrides") or {}, declared_slots, stage)
        profiles[str(stage)] = GammaStageProfile(
            stage=str(stage),
            label=str(item.get("label") or stage),
            template_id=str(item.get("template_id") or ""),
            cards=cards,
            pricing_permitted=pricing_permitted,
            client_logo=bool(item.get("client_logo")),
            fact_kinds=fact_kinds,
            slot_overrides=overrides,
        )
    return profiles


def _parse_slot_overrides(
    raw: dict[str, Any],
    declared_slots: set[str],
    stage: str,
) -> dict[str, GammaSlotOverride]:
    overrides: dict[str, GammaSlotOverride] = {}
    for name, item in raw.items():
        if name not in declared_slots:
            raise GammaTemplateContractError(
                f"stage_profiles.{stage} overrides unknown slot '{name}'."
            )
        if not isinstance(item, dict):
            raise GammaTemplateContractError(
                f"stage_profiles.{stage} override '{name}' must be an object."
            )
        chapter_ids = item.get("source_chapter_ids")
        max_chars = item.get("max_chars")
        overrides[str(name)] = GammaSlotOverride(
            source_chapter_ids=tuple(str(value) for value in chapter_ids)
            if chapter_ids is not None
            else None,
            max_chars=int(max_chars) if max_chars is not None else None,
        )
    return overrides
