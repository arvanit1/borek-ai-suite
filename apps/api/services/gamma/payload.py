"""ES-40 — Gamma content payload from a confirmed Framework plus retrieved facts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

from services.borek_rag.identity import live_provenance_marker
from services.framework.company_facts import (
    UngroundedPriceError,
    grounded_pricing_figures,
    live_answered_lookups,
    refuse_ungrounded_prices,
)
from services.gamma.contract import (
    FORBIDDEN_BRANDING_KEYS,
    LOCKED_BOREK_TEMPLATE_ID,
    LOCKED_BOREK_TEMPLATE_VERSION,
    GammaContentSlot,
    GammaPayloadError,
)
from services.gamma.slot_mapping import (
    DEFAULT_JOURNEY_STAGE,
    JOURNEY_STAGES,
    build_gamma_content_slots,
    resolve_journey_stage,
)
from services.gamma.template import GammaTemplate, load_gamma_template

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4] / "packages" / "contracts" / "gamma_payload.schema.json"
)


@lru_cache(maxsize=1)
def gamma_payload_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_gamma_content_payload(payload: dict[str, Any]) -> dict[str, Any]:
    jsonschema.validate(instance=payload, schema=gamma_payload_schema())
    names = [slot["name"] for slot in payload.get("slots") or []]
    if FORBIDDEN_BRANDING_KEYS & set(names) or any(name.startswith("brand.") for name in names):
        raise GammaPayloadError("Branding keys are locked in the Gamma template.")
    return payload


def build_gamma_content_payload(
    *,
    opportunity: dict[str, Any],
    framework: dict[str, Any] | None = None,
    template: GammaTemplate | None = None,
    stage: str | None = None,
    client_logo_ref: str | None = None,
) -> dict[str, Any]:
    """Named content slots plus grounded-fact provenance. No layout or styling."""
    resolved = resolve_journey_stage(stage)
    slots = build_gamma_content_slots(
        opportunity=opportunity,
        framework=framework,
        template=template or load_gamma_template(),
        stage=resolved,
    )
    grounding = _company_facts(framework)
    include_pricing = resolved == "concretisation"
    grounded = [
        _grounded_fact(lookup)
        for lookup in live_answered_lookups(
            grounding,
            include_pricing=include_pricing,
        )
    ]
    if include_pricing:
        _require_concretisation_pricing(framework, grounding)
    elif any(item["kind"] == "pricing" for item in grounded):
        raise GammaPayloadError("Pricing facts are only permitted on a Concretisation payload.")
    logo = None if resolved == "first_contact" else client_logo_ref
    payload = {
        "schema_version": "1.0",
        "template_id": LOCKED_BOREK_TEMPLATE_ID,
        "template_version": LOCKED_BOREK_TEMPLATE_VERSION,
        "stage": resolved,
        "slots": [{"name": slot.name, "value": slot.value} for slot in slots],
        "grounded_facts": grounded,
        "client_logo_ref": logo,
    }
    return validate_gamma_content_payload(payload)


def slots_from_payload(payload: dict[str, Any]) -> tuple[GammaContentSlot, ...]:
    return tuple(
        GammaContentSlot(name=str(item["name"]), value=str(item["value"]))
        for item in payload.get("slots") or []
    )


def _company_facts(framework: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(framework, dict):
        return None
    inner = framework.get("framework_json")
    if isinstance(inner, dict) and inner.get("generation_meta") is not None:
        return (inner.get("generation_meta") or {}).get("company_facts")
    return (framework.get("generation_meta") or {}).get("company_facts")


def _grounded_fact(lookup: dict[str, Any]) -> dict[str, Any]:
    source = (lookup.get("sources") or [{}])[0]
    return {
        "kind": lookup["kind"],
        "status": "answered",
        "statement": lookup.get("statement"),
        "payload": dict(lookup.get("payload") or {}),
        "provenance": {
            "corpus_id": source.get("corpus_id"),
            "corpus_version": source.get("corpus_version"),
            "document_id": source.get("document_id"),
            "document_type": source.get("document_type"),
            "document_version": source.get("document_version"),
            "fact_id": source.get("fact_id"),
            "marker": source.get("provenance_marker") or live_provenance_marker(),
        },
    }


def _require_concretisation_pricing(
    framework: dict[str, Any] | None,
    grounding: dict[str, Any] | None,
) -> None:
    figures = grounded_pricing_figures(grounding)
    for figure in figures:
        provenance = figure.get("provenance") or {}
        if not all(
            provenance.get(key)
            for key in ("corpus_id", "corpus_version", "document_id", "fact_id", "marker")
        ):
            raise GammaPayloadError(
                "Concretisation pricing is missing ES-39 provenance and is refused."
            )
    chapter_nine = _chapter_nine_text(framework)
    try:
        refuse_ungrounded_prices(
            text=chapter_nine,
            grounding=grounding,
            allow_prices=True,
        )
    except UngroundedPriceError as exc:
        raise GammaPayloadError(str(exc)) from exc


def _chapter_nine_text(framework: dict[str, Any] | None) -> str:
    if not isinstance(framework, dict):
        return ""
    inner = framework.get("framework_json") if isinstance(framework.get("framework_json"), dict) else framework
    chapters = (inner or {}).get("chapters") or []
    if not isinstance(chapters, list):
        return ""
    for chapter in chapters:
        if isinstance(chapter, dict) and str(chapter.get("chapter_id")) == "9":
            body = chapter.get("body")
            if isinstance(body, str):
                return body
            return json.dumps(body)
    return ""


# Re-export so BT-28 can import the frozen stage names from one module.
__all__ = [
    "DEFAULT_JOURNEY_STAGE",
    "JOURNEY_STAGES",
    "build_gamma_content_payload",
    "gamma_payload_schema",
    "slots_from_payload",
    "validate_gamma_content_payload",
]
