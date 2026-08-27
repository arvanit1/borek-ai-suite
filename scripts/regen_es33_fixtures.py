"""Regenerate ES-33 expected framework fixtures from deterministic pipeline."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "tests" / "eval" / "fixtures"
FROZEN_AT = "2026-08-26T10:00:00Z"

import sys

sys.path.insert(0, str(ROOT / "apps" / "api"))

from services.framework.pipeline import generate_customer_framework


def normalize(framework: dict, *, opportunity_id: str) -> dict:
    framework = json.loads(json.dumps(framework))
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
    manifest = json.loads((EVAL / "manifest.json").read_text(encoding="utf-8"))
    for case in manifest["cases"]:
        model = json.loads((ROOT / case["knowledge_model"]).read_text(encoding="utf-8"))
        overrides = json.loads((ROOT / case["engine_overrides"]).read_text(encoding="utf-8"))
        actual = generate_customer_framework(
            [model],
            opportunity_id=case["opportunity_id"],
            title_hint=case["title_hint"],
            use_llm=False,
            engine_overrides=overrides,
        )
        actual = normalize(actual, opportunity_id=case["opportunity_id"])
        out = ROOT / case["expected_framework"]
        out.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
