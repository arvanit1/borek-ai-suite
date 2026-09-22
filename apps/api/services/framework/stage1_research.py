"""BT-34 evidence-bound research; the LLM can write hypotheses, never facts."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from llm.claude.client import sonnet_model, structured_complete
from services.framework.company_facts import ground_company_facts
from services.framework.guardrails import semantic_numeric_values_in_text
from services.framework.stage1_intake import (
    SOURCE_RULE,
    format_stage1_intake_for_prompt,
    intake_from_opportunity,
    safe_intake_for_llm,
)
from services.observability.llm_logger import run_logged_llm_call

PROMPT_VERSION = "stage1-research:v1"
FACT_FIELDS = (
    "description",
    "headquarters",
    "employee_headcount",
    "decision_makers",
    "revenue",
)
SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "packages/contracts/stage1_research.schema.json"
)


@dataclass(frozen=True)
class CompanyEvidence:
    """An approved adapter must bind this evidence to the requested company.

    Value is an exact source excerpt, not an LLM paraphrase. Locator can be a
    document/page reference or a URL; this module never dereferences it.
    """

    field: str
    value: str
    source_id: str
    locator: str
    excerpt: str


class CompanyResearchProvider(Protocol):
    def research(
        self, *, client_name: str, client_website: str | None
    ) -> list[CompanyEvidence]: ...


def load_research_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_research(payload: dict[str, Any]) -> None:
    Draft202012Validator(
        load_research_schema(), format_checker=FormatChecker()
    ).validate(payload)


def _unknown_fact() -> dict[str, Any]:
    return {"status": "unknown", "origin": "UNKNOWN", "value": None, "source_refs": []}


def _unknown_hypothesis() -> dict[str, Any]:
    return {"status": "unknown", "origin": "AI_INFERENCE", "text": None, "basis": []}


def _company_facts(evidence: list[CompanyEvidence]) -> dict[str, Any]:
    # Validate every record before conflict resolution; malformed records must
    # not be hidden by an unknown field or a conflicting valid value.
    if not isinstance(evidence, list) or any(
        not isinstance(item, CompanyEvidence)
        or item.field not in FACT_FIELDS
        or not all(
            isinstance(value, str) and value.strip()
            for value in (item.value, item.source_id, item.locator, item.excerpt)
        )
        or item.value not in item.excerpt
        for item in evidence
    ):
        raise ValueError("Research provider returned unsupported evidence")
    facts = {field: _unknown_fact() for field in FACT_FIELDS}
    for field in FACT_FIELDS:
        entries = [item for item in evidence if item.field == field]
        # Conflicting sources remain unknown rather than silently choosing one.
        if not entries or len({item.value for item in entries}) != 1:
            continue
        facts[field] = {
            "status": "verified",
            "origin": "SOURCE_FACT",
            "value": entries[0].value,
            "source_refs": [
                {
                    "source_id": item.source_id,
                    "locator": item.locator,
                    "excerpt": item.excerpt,
                }
                for item in entries
            ],
        }
    return facts


def _borek_offering(subject: str, corpus: Any) -> dict[str, Any]:
    grounding = ground_company_facts(subject, corpus=corpus)
    service = next(
        (row for row in grounding["answered"] if row["kind"] == "service"), None
    )
    if not service or not service.get("statement") or not service.get("sources"):
        return _unknown_fact()
    refs = [
        {
            "source_id": str(source["fact_id"]),
            "locator": f"{source['corpus_version']}/{source['document_id']}",
            "excerpt": service["statement"],
        }
        for source in service["sources"]
    ]
    return {
        "status": "verified",
        "origin": "SOURCE_FACT",
        "value": service["statement"],
        "source_refs": refs,
    }


def generate_stage1_research(
    opportunity: dict[str, Any],
    *,
    corpus: Any = None,
    provider: CompanyResearchProvider | None = None,
    use_llm: bool = False,
    complete: Callable[[str, str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    intake = intake_from_opportunity(opportunity) or {
        "client_name": opportunity["client_name"]
    }
    evidence = (
        provider.research(
            client_name=opportunity["client_name"],
            client_website=intake.get("client_website"),
        )
        if provider is not None
        else []
    )
    facts = _company_facts(evidence)
    topic = intake.get("sales_topic_description")
    offering = _borek_offering(topic, corpus) if topic else _unknown_fact()
    result = {
        "schema_version": "1.0",
        "opportunity_id": str(opportunity["id"]),
        "client_name": opportunity["client_name"],
        "company_facts": facts,
        "user_statements": {"origin": "USER_INPUT", "fields": intake},
        "borek_offering": offering,
        "hypothesis": _unknown_hypothesis(),
        "product_relevance": _unknown_hypothesis(),
        "dependencies": [],
    }
    if provider is None:
        result["dependencies"].append("COMPANY_RESEARCH_PROVIDER_UNAVAILABLE")
    if offering["status"] == "unknown":
        result["dependencies"].append("BOREK_OFFERING_UNAVAILABLE")
    if not use_llm or not topic or offering["status"] == "unknown":
        result["dependencies"].append("HYPOTHESIS_GENERATION_NOT_RUN")
    else:
        schema = load_research_schema()
        tool_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["hypothesis", "product_relevance"],
            "properties": {
                key: {"$ref": "#/$defs/Hypothesis"}
                for key in ("hypothesis", "product_relevance")
            },
            "$defs": schema["$defs"],
        }
        system = (
            SOURCE_RULE
            + " Write only tentative Borek support and product-fit hypotheses. "
            "Use conditional language. Do not assert new client facts, headcount, revenue, "
            "decision-makers, prices, or quantified benefits. The offering is Borek's, not the client's. "
            "Use basis identifiers stage1_intake.sales_topic_description and borek_offering. "
            "If evidence is insufficient return unknown. Return JSON matching the schema."
        )
        safe = safe_intake_for_llm(
            intake, redact=opportunity.get("pii_redaction_enabled", True)
        )
        user = (
            format_stage1_intake_for_prompt(safe)
            + "\nBOREK_OFFERING:\n"
            + json.dumps(offering)
        )
        usage: list[Any] = []

        def invoke() -> dict[str, Any]:
            output = (
                complete(system, user, copy.deepcopy(tool_schema))
                if complete
                else structured_complete(
                    system,
                    user,
                    tool_schema,
                    tool_name="submit_stage1_hypotheses",
                    tool_description="Submit explicitly tentative support and product-fit hypotheses.",
                    max_tokens=4096,
                    usage_out=usage,
                )
            )
            try:
                Draft202012Validator(tool_schema).validate(output)
            except ValidationError as exc:
                # ES-32 records exception messages; never put model/source text there.
                raise ValueError(
                    "Stage 1 hypothesis output failed schema validation"
                ) from exc
            for hypothesis in output.values():
                if set(hypothesis["basis"]) - {
                    "stage1_intake.sales_topic_description",
                    "borek_offering",
                }:
                    raise ValueError("Hypothesis cites unavailable evidence")
                source_text = " ".join(
                    (
                        topic
                        if ref == "stage1_intake.sales_topic_description"
                        else offering["value"]
                    )
                    for ref in hypothesis["basis"]
                )
                unsupported = semantic_numeric_values_in_text(
                    hypothesis["text"] or ""
                ) - semantic_numeric_values_in_text(source_text)
                if unsupported:
                    raise ValueError("Hypothesis contains unsupported numeric claims")
            return output

        generated = run_logged_llm_call(
            stage="stage1_research",
            prompt_version=PROMPT_VERSION,
            model="fixture" if complete else sonnet_model(),
            attempt=1,
            opportunity_id=str(opportunity["id"]),
            usage_out=usage,
            invoke=invoke,
        )
        result.update(generated)
    validate_research(result)
    return result
