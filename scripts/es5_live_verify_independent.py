"""Live ES-5 extraction verification for es23_independent_*.txt transcripts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402 — loads .env
from services.framework.assembly import assemble_from_knowledge
from services.framework.pipeline import generate_customer_framework, run_engines
from services.knowledge_model.extraction import extract_knowledge_model
from services.knowledge_model.source_refs import iter_knowledge_entries
from services.transcript.conversation_ids import allocate_opportunity_id, allocate_transcript_identity
from services.transcript.speaker_turns import split_speaker_turns

TRANSCRIPTS = sorted((ROOT / "sample_transcripts").glob("es23_independent_*.txt"))

NUMBER_HINTS = (
    r"\d[\d,]*\s*(?:staff-)?h(?:ours?)?",
    r"\d[\d,]*\s+(?:vendor invoices|invoices|tickets|units|RMA|hires|new hires)",
    r"(?:six hundred|forty|2,400|670)",
    r"\d+\s+euros?\s+an?\s+h(?:our)?",
    r"EUR\s*\d+",
    r"\d+\s+percent",
    r"under\s+\d+\s+hours",
    r"down to\s+\d+\s+hours",
    r"capped at\s+\d+\s+hours",
    r"90 hours of human touch",
)
HINT_RE = re.compile("|".join(NUMBER_HINTS), re.I)


def _transcript_number_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for line in text.splitlines():
        if ": " not in line:
            continue
        utterance = line.split(": ", 1)[1].strip()
        if HINT_RE.search(utterance):
            sentences.append(utterance)
    return sentences


def _entries_with_metrics(model: dict) -> list[dict]:
    rows: list[dict] = []
    for bucket, _index, entry in iter_knowledge_entries(model):
        metric = entry.get("metric")
        if metric or HINT_RE.search(str(entry.get("statement") or "")):
            rows.append(
                {
                    "bucket": bucket,
                    "statement": entry.get("statement"),
                    "metric": metric,
                    "origin": entry.get("origin"),
                    "confidence": entry.get("confidence"),
                    "source_refs": entry.get("source_refs"),
                }
            )
    return rows


def _ch9_table(framework: dict) -> list[list]:
    ch9 = next(ch for ch in framework["chapters"] if str(ch.get("chapter_id")) == "9")
    table = next(b for b in ch9["body"] if b.get("block") == "table")
    return table["rows"]


def main() -> None:
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY missing — cannot run live ES-5 verification.")

    print("ANTHROPIC_MODEL:", settings.anthropic_model)
    print("TRANSCRIPTS:", len(TRANSCRIPTS))
    print()

    for path in TRANSCRIPTS:
        print("=" * 100)
        print("FILE:", path.name)
        print("=" * 100)
        raw_text = path.read_text(encoding="utf-8")
        print("\n--- Transcript sentences with business numbers (grep) ---")
        for sentence in _transcript_number_sentences(raw_text):
            print(" ", json.dumps(sentence, ensure_ascii=False))

        turns = split_speaker_turns(path.name, raw_text.encode("utf-8"))
        opp = allocate_opportunity_id(None)
        identity = allocate_transcript_identity(opp, conversation_id="C1", taken_conversation_ids=[])
        print(f"\n--- ES-5 live extraction ({len(turns)} turns) ---")
        model = extract_knowledge_model(turns, identity, redact=True)
        print(json.dumps(model, indent=2, ensure_ascii=False))

        print("\n--- Entries with metrics or numeric statements (raw fields) ---")
        for row in _entries_with_metrics(model):
            print(json.dumps(row, indent=2, ensure_ascii=False))

        model_for_pipeline = {k: v for k, v in model.items() if k != "opportunity_id"}
        skeleton = assemble_from_knowledge([model_for_pipeline], opportunity_id=f"OPP-{path.stem}")
        engines = run_engines(skeleton, overrides={})
        framework = generate_customer_framework(
            [model_for_pipeline],
            opportunity_id=f"OPP-{path.stem}",
            title_hint=path.stem,
            use_llm=False,
        )

        print("\n--- engine_inputs ---")
        keys = (
            "monthly_volume",
            "automatable_hours_mo",
            "target_remaining_hours_mo",
            "loaded_hourly_cost_eur",
            "automation_rate",
            "unresolved_fields",
        )
        print(json.dumps({k: skeleton["engine_inputs"].get(k) for k in keys}, indent=2))

        print("\n--- business_case ---")
        bc = engines["business_case"]
        print(
            json.dumps(
                {
                    "hours_saved_mo": bc.get("hours_saved_mo"),
                    "gross_eur_mo": bc.get("gross_eur_mo"),
                    "net_eur_mo": bc.get("net_eur_mo"),
                    "inputs": bc.get("inputs"),
                },
                indent=2,
            )
        )

        print("\n--- Chapter 9 table rows ---")
        for row in _ch9_table(framework):
            print(" ", row)

        print("\n--- Financial open items ---")
        for item in skeleton.get("open_items") or []:
            desc = str(item.get("description") or "")
            if any(token in desc.lower() for token in ("ai-inferred", "not parsed", "mentioned in conversation")):
                print(" ", json.dumps(item, ensure_ascii=False))
        print()


if __name__ == "__main__":
    main()
