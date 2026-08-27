"""Assert live ES-5 → engine_inputs → Ch.9 for es23_independent transcripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from services.framework.assembly import assemble_from_knowledge
from services.framework.pipeline import generate_customer_framework, run_engines
from services.knowledge_model.extraction import extract_knowledge_model
from services.transcript.conversation_ids import allocate_opportunity_id, allocate_transcript_identity
from services.transcript.speaker_turns import split_speaker_turns

EXPECTED = {
    "es23_independent_customer_refunds.txt": {
        "vol": 2400,
        "auto": 320,
        "target": 90,
        "hourly": 41,
        "saved": 230,
        "forbidden": ("8812",),
    },
    "es23_independent_hr_onboarding.txt": {
        "vol": 40,
        "auto": 180,
        "target": 50,
        "hourly": 35,
        "saved": 130,
        "forbidden": ("2022", "555"),
    },
    "es23_independent_invoice_ap.txt": {
        "vol": 600,
        "auto": 110,
        "target": 30,
        "hourly": 52,
        "saved": 80,
        "forbidden": ("14", "4421", "March"),
    },
    "es23_independent_warehouse_returns.txt": {
        "vol": 670,
        "auto": 88,
        "target": 25,
        "hourly": 29,
        "saved": 63,
        "forbidden": ("018", "2019"),
    },
}


def main() -> None:
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY missing — cannot run live verification.")

    failures: list[str] = []
    for path in sorted((ROOT / "sample_transcripts").glob("es23_independent_*.txt")):
        name = path.name
        exp = EXPECTED[name]
        text = path.read_text(encoding="utf-8")
        opp = allocate_opportunity_id(None)
        identity = allocate_transcript_identity(opp, conversation_id="C1", taken_conversation_ids=[])
        turns = split_speaker_turns(name, text.encode("utf-8"))
        km = extract_knowledge_model(turns, identity, redact=True)
        model = {k: v for k, v in km.items() if k != "opportunity_id"}
        skeleton = assemble_from_knowledge([model], opportunity_id=opp, title_hint=name)
        inputs = skeleton["engine_inputs"]
        business = run_engines(skeleton, overrides={})["business_case"]
        framework = generate_customer_framework([model], opportunity_id=opp, title_hint=name, use_llm=False)
        ch9 = json.dumps(
            next(ch for ch in framework["chapters"] if str(ch.get("chapter_id")) == "9"),
            ensure_ascii=False,
        )

        for label, got, want in (
            ("volume", inputs.get("monthly_volume"), exp["vol"]),
            ("automatable", inputs.get("automatable_hours_mo"), exp["auto"]),
            ("target", inputs.get("target_remaining_hours_mo"), exp["target"]),
            ("hourly", inputs.get("loaded_hourly_cost_eur"), exp["hourly"]),
            ("saved", business.get("hours_saved_mo"), exp["saved"]),
            ("biz_auto", business["inputs"].get("automatable_hours_mo"), exp["auto"]),
        ):
            if got != want:
                failures.append(f"{name}: {label} got {got!r} want {want!r}")

        unresolved = inputs.get("unresolved_fields") or []
        if unresolved:
            failures.append(f"{name}: unresolved_fields={unresolved!r}")

        if inputs.get("automatable_hours_mo") != business["inputs"].get("automatable_hours_mo"):
            failures.append(f"{name}: engine_inputs vs business_case automatable mismatch")

        for token in exp["forbidden"]:
            if token in ch9:
                failures.append(f"{name}: decoy {token!r} leaked into ch9")

        if str(exp["saved"]) not in ch9:
            failures.append(f"{name}: hours_saved {exp['saved']} not visible in ch9")

    if failures:
        print(f"FAILED: {len(failures)} assertion(s)")
        for item in failures:
            print(f"  - {item}")
        raise SystemExit(1)

    print("LIVE VERIFY: 4/4 transcripts PASS all assertions")
    print(f"Model: {settings.anthropic_model}")
    print(f"API key: present ({len(settings.anthropic_api_key)} chars)")


if __name__ == "__main__":
    main()
