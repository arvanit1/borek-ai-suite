# ES-33 — eval fixture transcript set

Hand-verified **expected FrameworkObject** outputs for deterministic customer-report generation (builder path, no live Claude).

## Layout

```
tests/eval/fixtures/
  manifest.json                 # index of all cases
  transcripts/                  # source transcripts (2–3)
  knowledge_models/             # KM inputs for eval-only cases
  engine_overrides/             # engine tuning for reproducible scores/ROI
  expected/                     # golden FrameworkObject JSON (14 chapters each)
```

## Cases (3)

| ID | Transcript | Notes |
|----|------------|-------|
| `invoice_3way_match` | Rich AP 3-way match | Uses `packages/contracts/fixtures/knowledge_model.invoice_3way.json` |
| `minimal_invoice_match` | Small AP team, 200/mo | Sample gap, human approval on every posting |
| `warehouse_delivery_match` | Warehouse delivery notes | SAP read-only, write + samples open |

## Regenerate expected outputs

After intentional pipeline changes, refresh goldens:

```bash
py -3 scripts/build_es33_fixtures.py
```

Review the diff, then commit. Expected files use frozen timestamps (`2026-08-26T10:00:00Z`) and deterministic builder output (`use_llm=False`).

## Verification

`tests/unit/eval/test_es33_fixtures.py` checks:

- manifest lists 2–3 cases
- each transcript + expected file exists
- each expected object has **14 chapters** and validates against `framework_object.schema.json`
- regenerating from KM + overrides matches the checked-in expected file
