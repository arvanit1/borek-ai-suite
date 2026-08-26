"""Build or refresh ES-33 hand-verified expected FrameworkObject fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from services.framework.pipeline import generate_customer_framework  # noqa: E402

EVAL = ROOT / "tests" / "eval" / "fixtures"
CONTRACTS = ROOT / "packages" / "contracts" / "fixtures"
FROZEN_AT = "2026-08-26T10:00:00Z"

CASES = [
    {
        "id": "invoice_3way_match",
        "transcript": EVAL / "transcripts" / "invoice_3way_match.txt",
        "knowledge_model": CONTRACTS / "knowledge_model.invoice_3way.json",
        "engine_overrides": CONTRACTS / "engine_overrides.invoice_3way.json",
        "opportunity_id": "OPP-142",
        "title_hint": "Invoice 3-Way Match",
        "verified_notes": "Rich AP case with rules, security, ROI, and stage-2 recommendation.",
    },
    {
        "id": "minimal_invoice_match",
        "transcript": EVAL / "transcripts" / "minimal_invoice_match.txt",
        "knowledge_model": EVAL / "knowledge_models" / "minimal_invoice_match.km.json",
        "engine_overrides": EVAL / "engine_overrides" / "minimal_invoice_match.json",
        "opportunity_id": "OPP-MIN-001",
        "title_hint": "Minimal AP Invoice Match",
        "verified_notes": "Small-team case with sample gap and human approval on every posting.",
    },
    {
        "id": "warehouse_delivery_match",
        "transcript": EVAL / "transcripts" / "warehouse_delivery_match.txt",
        "knowledge_model": EVAL / "knowledge_models" / "warehouse_delivery_match.km.json",
        "engine_overrides": EVAL / "engine_overrides" / "warehouse_delivery_match.json",
        "opportunity_id": "OPP-WARE-001",
        "title_hint": "Warehouse Delivery-Note Match",
        "verified_notes": "Write path and sample gaps; open dependencies expected in chapter 11.",
    },
]


def _normalize(framework: dict, *, opportunity_id: str) -> dict:
    framework.pop("customer_view", None)
    framework_id = f"FW-{opportunity_id}-v1"
    framework["id"] = framework_id
    framework["framework_id"] = framework_id
    framework["created_at"] = FROZEN_AT
    framework["updated_at"] = FROZEN_AT
    meta = framework.get("generation_meta") or {}
    meta["generated_at"] = FROZEN_AT
    meta["llm_job_log"] = []
    meta["llm_used"] = False
    meta["llm_model"] = "deterministic-builder"
    framework["generation_meta"] = meta
    return framework


def main() -> None:
    expected_dir = EVAL / "expected"
    expected_dir.mkdir(parents=True, exist_ok=True)
    manifest_cases = []

    for case in CASES:
        model = json.loads(case["knowledge_model"].read_text(encoding="utf-8"))
        overrides = json.loads(case["engine_overrides"].read_text(encoding="utf-8"))
        framework = generate_customer_framework(
            [model],
            opportunity_id=case["opportunity_id"],
            title_hint=case["title_hint"],
            use_llm=False,
            engine_overrides=overrides,
        )
        framework = _normalize(framework, opportunity_id=case["opportunity_id"])
        out = expected_dir / f"{case['id']}.framework.json"
        out.write_text(json.dumps(framework, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest_cases.append(
            {
                "id": case["id"],
                "transcript": str(case["transcript"].relative_to(ROOT)).replace("\\", "/"),
                "knowledge_model": str(case["knowledge_model"].relative_to(ROOT)).replace("\\", "/"),
                "engine_overrides": str(case["engine_overrides"].relative_to(ROOT)).replace("\\", "/"),
                "expected_framework": str(out.relative_to(ROOT)).replace("\\", "/"),
                "opportunity_id": case["opportunity_id"],
                "title_hint": case["title_hint"],
                "verified_notes": case["verified_notes"],
                "verified_at": FROZEN_AT,
                "verified_by": "ES-33 fixture build (deterministic builder, hand-reviewed structure)",
            }
        )
        print(f"Wrote {out.relative_to(ROOT)} ({len(framework['chapters'])} chapters)")

    manifest = {
        "schema_version": "1.0",
        "ticket": "ES-33",
        "description": "Hand-verified expected FrameworkObject outputs for eval transcripts.",
        "cases": manifest_cases,
    }
    (EVAL / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote manifest with {len(manifest_cases)} cases")


if __name__ == "__main__":
    main()
