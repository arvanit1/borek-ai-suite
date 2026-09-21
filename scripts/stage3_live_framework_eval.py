"""Stage 3 live Claude eval: one transcript → Knowledge Model → Framework.

Uses ANTHROPIC_API_KEY from repo .env. Does not print the key.
One extraction call plus one 14-chapter synthesis call.

    py -3 scripts/stage3_live_framework_eval.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from packages.contracts.schema_consumer import validate_framework_object  # noqa: E402
from services.framework.chapter_validators import validate_all_chapters  # noqa: E402
from services.framework.chapter_validators.base import ChapterValidationError  # noqa: E402
from services.framework.pipeline import generate_customer_framework  # noqa: E402
from services.knowledge_model.extraction import extract_knowledge_model  # noqa: E402
from services.transcript.conversation_ids import allocate_opportunity_id, allocate_transcript_identity  # noqa: E402
from services.transcript.speaker_turns import split_speaker_turns  # noqa: E402

TRANSCRIPT = ROOT / "sample_transcripts" / "es23_independent_invoice_ap.txt"
OUT_DIR = ROOT / "generated" / "stage3_live_eval"
KM_PATH = OUT_DIR / "last_knowledge_model.json"
IDENTIFIER_MARKERS = ("061985", "OPP-061985", "opp-061985")


def _public_error(exc: BaseException) -> str:
    text = str(getattr(exc, "user_message", None) or exc)
    lowered = text.lower()
    if "credit" in lowered or "billing" in lowered or "quota" in lowered or "insufficient" in lowered:
        return "Anthropic refused the call (credits/billing). Stopped without a second attempt."
    if "api_key" in lowered or "authentication" in lowered or "unauthorized" in lowered:
        return "Anthropic rejected the API key."
    return text[:400]


def main() -> int:
    if not settings.anthropic_api_key:
        print("ANTHROPIC_API_KEY is missing in .env")
        return 2

    print("model:", settings.anthropic_model)
    print("transcript:", TRANSCRIPT.name)
    print("started:", datetime.now(timezone.utc).isoformat())

    raw = TRANSCRIPT.read_bytes()
    turns = split_speaker_turns(TRANSCRIPT.name, raw)
    opp = allocate_opportunity_id(None)
    identity = allocate_transcript_identity(opp, conversation_id="C1", taken_conversation_ids=[])
    print(f"turns: {len(turns)}")

    t0 = time.perf_counter()
    reuse_km = "--reuse-km" in sys.argv or os.environ.get("STAGE3_REUSE_KM") == "1"
    if reuse_km and KM_PATH.exists():
        print("reusing saved Knowledge Model (no extraction call)")
        model = json.loads(KM_PATH.read_text(encoding="utf-8"))
        extract_s = 0.0
        print(f"extraction_ok in {extract_s:.1f}s facts={len(model.get('facts') or [])} reused=true")
    else:
        try:
            print("ES-5 extraction starting (live Claude)...")
            model = extract_knowledge_model(turns, identity, redact=True)
        except Exception as exc:
            print("extraction_failed:", _public_error(exc))
            traceback.print_exc()
            return 1
        extract_s = time.perf_counter() - t0
        print(f"extraction_ok in {extract_s:.1f}s facts={len(model.get('facts') or [])}")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        KM_PATH.write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")

    t1 = time.perf_counter()
    try:
        print("ES-9 synthesis starting (live Claude, 14 chapters)...")
        model_for_pipeline = {key: value for key, value in model.items() if key != "opportunity_id"}
        framework = generate_customer_framework(
            [model_for_pipeline],
            opportunity_id=f"OPP-{TRANSCRIPT.stem}",
            title_hint="Independent AP invoice match",
            use_llm=True,
        )
    except Exception as exc:
        print("synthesis_failed:", _public_error(exc))
        traceback.print_exc()
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "last_knowledge_model.json").write_text(
            json.dumps(model, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return 1
    synthesis_s = time.perf_counter() - t1

    schema_ok = True
    schema_error = ""
    try:
        validate_framework_object(framework)
    except Exception as exc:
        schema_ok = False
        schema_error = str(exc)[:400]

    chapter_ok = True
    chapter_error = ""
    try:
        leftover = validate_all_chapters(framework)
        if leftover:
            chapter_ok = False
            chapter_error = "; ".join(f"{issue.chapter_id}:{issue.code}" for issue in leftover)
    except ChapterValidationError as exc:
        chapter_ok = False
        chapter_error = exc.user_message[:600]

    chapters = framework.get("chapters") or []
    chapter_ids = [str(chapter.get("chapter_id")) for chapter in chapters]
    open_blob = json.dumps(framework.get("open_items") or [])
    identifier_hits = [marker for marker in IDENTIFIER_MARKERS if marker in open_blob]
    business = framework.get("business_case") or {}
    scores = framework.get("quality_scores") or {}

    summary = {
        "transcript": TRANSCRIPT.name,
        "model": settings.anthropic_model,
        "extract_seconds": round(extract_s, 1),
        "synthesis_seconds": round(synthesis_s, 1),
        "chapter_count": len(chapters),
        "chapter_ids": chapter_ids,
        "schema_ok": schema_ok,
        "schema_error": schema_error,
        "chapters_ok": chapter_ok,
        "chapter_error": chapter_error,
        "llm_used": bool((framework.get("generation_meta") or {}).get("llm_used")),
        "identifier_hits": identifier_hits,
        "business_case_grounded": business.get("grounded"),
        "quality_scores": {
            key: scores.get(key)
            for key in ("opportunity_rating", "conversation_quality", "build_readiness")
        },
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "last_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT_DIR / "last_framework.json").write_text(
        json.dumps(framework, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    if not schema_ok or not chapter_ok or len(chapters) != 14 or identifier_hits:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
