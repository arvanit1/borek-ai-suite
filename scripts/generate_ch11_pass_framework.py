"""Build a complete KM from the Chapter 11 pass transcript and generate a Framework.

Deterministic (use_llm=False) so Claude shape/paraphrase cannot fail-close.
Empty company_facts so AT-59 corpus misses do not add Commercial rows.

    uv run python scripts/generate_ch11_pass_framework.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT))

from packages.contracts.schema_consumer import validate_framework_object
from services.framework.chapter_validators import validate_all_chapters
from services.framework.pipeline import generate_customer_framework
from services.framework.quality_scores import green_light
from services.knowledge_model.entry_ids import ensure_knowledge_entry_ids

OUT_DIR = ROOT / "generated" / "ch11_pass"
TRANSCRIPT = ROOT / "sample_transcripts" / "ch11_quality_gates_pass.txt"


def _ref(turn: int, speaker: str = "Maria") -> list[dict[str, str]]:
    return [
        {
            "conversation_id": "C1",
            "speaker_role": speaker,
            "excerpt_pointer": f"turn:{turn}",
        }
    ]


def _entry(
    statement: str,
    *,
    turn: int,
    speaker: str = "Maria",
    origin: str = "SOURCE_FACT",
    metric: dict | None = None,
) -> dict:
    row: dict = {
        "statement": statement,
        "origin": origin,
        "confidence": "high",
        "source_refs": _ref(turn, speaker),
    }
    if metric:
        row["metric"] = metric
    return row


def build_knowledge_model() -> dict:
    model = {
        "schema_version": "1.0",
        "prompt_version": "framework-extraction:v1",
        "opportunity_id": "OPP-CH11-PASS",
        "transcript_id": "transcript-ch11-pass",
        "conversation_id": "C1",
        "facts": [
            _entry(
                "Nordlicht Components processes 850 vendor invoices per month.",
                turn=1,
                metric={"kind": "monthly_volume", "value": 850, "unit": "invoices"},
            ),
            _entry(
                "Clerks spend 210 staff-hours on the matchable portion each month.",
                turn=1,
                metric={"kind": "automatable_hours_mo", "value": 210, "unit": "hours"},
            ),
            _entry(
                "The full AP desk is about 310 hours each month.",
                turn=1,
                metric={"kind": "team_hours_mo", "value": 310, "unit": "hours"},
            ),
            _entry(
                "Fully loaded clerk rate is 52 euros an hour.",
                turn=2,
                metric={"kind": "loaded_hourly_cost_eur", "value": 52, "unit": "EUR/hour"},
            ),
            _entry(
                "At 52 euros an hour the full AP desk is 16,120 euros each month.",
                turn=2,
            ),
            _entry(
                "The estimated build is four weeks.",
                turn=2,
            ),
            _entry(
                "A sample of 200 anonymized invoices from last quarter is available.",
                turn=6,
                speaker="IT",
            ),
            _entry(
                "SSO is already configured with Microsoft Entra ID.",
                turn=6,
                speaker="IT",
            ),
            _entry(
                "The rule-confirmation workshop is scheduled for 2 October 2026.",
                turn=6,
                speaker="IT",
            ),
        ],
        "stated_requirements": [
            _entry(
                "This is approved scope and a committed priority for the next quarter.",
                turn=1,
                origin="USER_INPUT",
            ),
            _entry(
                "Goal is to reduce clerical load from 210 hours to 25 hours per month.",
                turn=2,
                origin="USER_INPUT",
                metric={"kind": "target_remaining_hours_mo", "value": 25, "unit": "hours"},
            ),
            _entry(
                "Success is measured via SAP posting logs. Target remaining hours is 25 hours per month.",
                turn=8,
                origin="USER_INPUT",
            ),
            _entry(
                "Automation rate for clean matches is a signed 0.70 once the four-week path is live.",
                turn=8,
                origin="USER_INPUT",
                metric={"kind": "automation_rate", "value": 0.70, "unit": "fraction"},
            ),
        ],
        "constraints": [
            _entry(
                "Personal data stays in the EU. GDPR retention is 30 days for logs.",
                turn=7,
                speaker="Quality",
                origin="USER_INPUT",
            ),
            _entry(
                "Classification is internal confidential. Least-privilege service account.",
                turn=7,
                speaker="Quality",
                origin="USER_INPUT",
            ),
        ],
        "named_systems": [
            _entry(
                "SAP S/4HANA read and write access is live via BAPI. Approval was granted.",
                turn=6,
                speaker="IT",
            ),
            _entry(
                "Outlook mailbox read access is live for the AP inbox via Microsoft Graph.",
                turn=6,
                speaker="IT",
            ),
            _entry(
                "The vendor portal is available for certificate read over HTTPS.",
                turn=6,
                speaker="IT",
            ),
        ],
        "named_rules": [
            _entry(
                "Quantity matches exactly across invoice, purchase order, and goods receipt.",
                turn=4,
            ),
            _entry(
                "Unit price matches exactly when a stored discount agreement applies.",
                turn=4,
            ),
            _entry(
                "Total rounding tolerance is 0.50 euros.",
                turn=4,
            ),
            _entry(
                "Amount deviation versus the purchase order greater than 2 percent is held for review.",
                turn=4,
            ),
            _entry(
                "Human one-click confirmation is required before any SAP posting or supplier mail.",
                turn=5,
            ),
        ],
        "named_exceptions": [
            _entry(
                "Exceptions are mixed-line invoices, missing goods receipts, and price variances. Those cases are 8 percent of the batch and go to the AP supervisor queue.",
                turn=5,
                metric={"kind": "exception_rate_pct", "value": 8, "unit": "percent"},
            ),
        ],
        "people_and_roles": [
            _entry("Maria Keller is AP lead at Nordlicht Components in Leipzig.", turn=1),
            _entry("Exception cases go to the AP supervisor queue.", turn=5),
        ],
        "timeline_mentions": [
            _entry("Finance started this initiative in March 2024.", turn=2),
            _entry("The estimated build is four weeks.", turn=2),
            _entry("The rule-confirmation workshop is scheduled for 2 October 2026.", turn=6, speaker="IT"),
        ],
        "risks": [
            _entry(
                "Every suggested match is logged with a reason code and monitored. Processing is protected.",
                turn=7,
                speaker="Quality",
            ),
        ],
        "unknowns": [],
        "conflicts": [],
    }
    ensure_knowledge_entry_ids(model)
    return model


def main() -> int:
    if not TRANSCRIPT.exists():
        print("missing transcript:", TRANSCRIPT)
        return 2
    model = build_knowledge_model()
    framework = generate_customer_framework(
        [model],
        opportunity_id="OPP-CH11-PASS",
        title_hint="Nordlicht AP three-way match",
        use_llm=False,
        company_facts={"subject": "Nordlicht AP three-way match", "lookups": [], "answered": [], "unknown": []},
    )
    validate_framework_object(framework)
    validate_all_chapters(framework)
    scores = framework.get("quality_scores") or {}
    gate = green_light(
        int(scores.get("opportunity_rating") or 0),
        int(scores.get("conversation_quality") or 0),
        int(scores.get("build_readiness") or 0),
    )
    ch11 = next(ch for ch in framework["chapters"] if str(ch.get("chapter_id")) == "11")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "knowledge_model.json").write_text(json.dumps(model, indent=2), encoding="utf-8")
    (OUT_DIR / "framework.json").write_text(json.dumps(framework, indent=2), encoding="utf-8")
    (OUT_DIR / "chapter_11.json").write_text(json.dumps(ch11, indent=2), encoding="utf-8")
    (OUT_DIR / "transcript.txt").write_text(TRANSCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    print("transcript:", TRANSCRIPT)
    print("output:", OUT_DIR / "framework.json")
    print("quality_scores:", json.dumps(scores, indent=2))
    print("green_light:", gate)
    print("open_items:", len(framework.get("open_items") or []))
    print("chapters:", len(framework.get("chapters") or []))
    print("schema_ok: true")
    print("chapters_ok: true")
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
