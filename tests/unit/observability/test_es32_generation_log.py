"""ES-32 — prompt version stored on generation-job log."""

from __future__ import annotations

import json
from pathlib import Path

from services.framework.pipeline import generate_customer_framework
from services.framework.synthesis import PROMPT_VERSION as SYNTHESIS_PROMPT_VERSION
from services.knowledge_model.extraction import PROMPT_VERSION as EXTRACTION_PROMPT_VERSION, extract_knowledge_model
from services.observability.llm_logger import (
    STAGE_EXTRACTION,
    STAGE_SYNTHESIS,
    clear_generation_jobs,
    jobs_for_opportunity,
    log_generation_job,
)
from services.transcript.conversation_ids import TranscriptIdentity
from services.transcript.speaker_turns import SpeakerTurn

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures"


def test_es32_log_entry_stores_prompt_version_and_stage() -> None:
    clear_generation_jobs()
    entry = log_generation_job(
        stage=STAGE_SYNTHESIS,
        prompt_version=SYNTHESIS_PROMPT_VERSION,
        model="claude-sonnet-4-5",
        status="success",
        attempt=1,
        opportunity_id="OPP-1",
    )
    assert entry["prompt_version"] == "framework-synthesis:v1"
    assert entry["stage"] == STAGE_SYNTHESIS
    assert entry["request_id"].startswith("gen-")


def test_es32_extraction_logs_prompt_version_on_live_path() -> None:
    clear_generation_jobs()
    turns = [SpeakerTurn(0, "Sandra", "We match invoices in the ERP.")]
    identity = TranscriptIdentity(opportunity_id="OPP-32", transcript_id="T-1", conversation_id="C1")

    def complete(system: str, user: str, schema: dict) -> dict:
        return {
            "facts": [
                {
                    "statement": "Invoices are matched in the ERP.",
                    "origin": "SOURCE_FACT",
                    "confidence": "high",
                    "source_refs": [
                        {
                            "conversation_id": "C1",
                            "speaker_role": "Sandra",
                            "excerpt_pointer": "turn:0",
                        }
                    ],
                }
            ],
            "stated_requirements": [],
            "constraints": [],
            "named_systems": [],
            "named_rules": [],
            "named_exceptions": [],
            "people_and_roles": [],
            "timeline_mentions": [],
            "risks": [],
            "unknowns": [],
        }

    extract_knowledge_model(turns, identity, complete=complete)
    jobs = jobs_for_opportunity("OPP-32", stages=[STAGE_EXTRACTION])
    assert jobs == []


def test_es32_synthesis_generation_meta_includes_job_log() -> None:
    clear_generation_jobs()
    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    overrides = json.loads((FIXTURES / "engine_overrides.invoice_3way.json").read_text(encoding="utf-8"))
    base = generate_customer_framework(
        [model],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    draft = {
        "title": base["title"],
        "department": base["department"],
        "cover": {
            "tagline": "Customer framework report.",
            "sources_line": "Sources C6",
            "how_produced": "Generated from conversations.",
        },
        "kpis": [],
        "systems": [],
        "rules": [],
        "exceptions": [],
        "access_needs": [],
        "open_items": [],
        "chapters": [
            {
                "chapter_id": chapter["chapter_id"],
                "title": chapter["title"],
                "body": chapter["body"],
                "source_refs": chapter.get("source_refs")
                or [
                    {
                        "conversation_id": "C6",
                        "speaker_role": "Sandra",
                        "excerpt_pointer": "turn:0",
                    }
                ],
            }
            for chapter in base["chapters"]
        ],
    }

    def complete(system: str, user: str, schema: dict) -> dict:
        log_generation_job(
            stage=STAGE_SYNTHESIS,
            prompt_version=SYNTHESIS_PROMPT_VERSION,
            model="claude-sonnet-4-5",
            status="success",
            attempt=1,
            opportunity_id="OPP-142",
        )
        return draft

    framework = generate_customer_framework(
        [model],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=True,
        complete=complete,
        engine_overrides=overrides,
    )
    log = framework["generation_meta"]["llm_job_log"]
    assert len(log) == 1
    assert log[0]["prompt_version"] == SYNTHESIS_PROMPT_VERSION
    assert log[0]["stage"] == STAGE_SYNTHESIS


def test_prompt_versions_match_prompt_files() -> None:
    prompts = Path(__file__).resolve().parents[3] / "apps" / "api" / "llm" / "claude" / "prompts"
    assert EXTRACTION_PROMPT_VERSION == prompts.joinpath("extraction_v1.txt").read_text(encoding="utf-8").splitlines()[0]
    assert SYNTHESIS_PROMPT_VERSION == prompts.joinpath("synthesis_v1.txt").read_text(encoding="utf-8").splitlines()[0]
