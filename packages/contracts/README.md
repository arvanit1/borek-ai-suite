# packages/contracts ù Canonical JSON Schemas (SSOT)

Single source of truth for all cross-service data contracts.

| Schema | Ticket | Status |
|--------|--------|--------|
| `framework_object.schema.json` | AT-1 | Complete |
| `presentation_plan.schema.json` | AT-2 | Complete |
| `slide_spec/base.schema.json` | AT-3 | Complete |
| Pydantic codegen (`scripts/generate_pydantic.py`) | AT-4 | Complete |
| TypeScript codegen (`scripts/generate_typescript.js`) | AT-5 | Complete |
| Schema consumers (`schema_consumer.py`) | AT-6 | Complete |
| `chapter_registry.json` | AT-1 (section 8) | Complete |
| `layout_registry.json` | section 13.1 / BT-2 prep | Complete |
| `chapter_layout_map.json` | BT-3 prep | Complete |
| `slide_spec/group_*/*.schema.json` | BT/JJ/MS | Pending |
| `knowledge_model.schema.json` | ES-5 (Endrit) | Pending |

## Validation gate

Run from repo root:

```bash
py -3 scripts/validate_all.py
```

Must pass before marking schema tickets complete:
- contract unit tests under `tests/unit/contracts/`
- AT-7 constraint validator tests (`tests/unit/validation/test_constraint_validator.py`)
- AT-8 compression/retry tests (`tests/unit/validation/test_compression_retry.py`)
- AT-9 LibreOffice preview pipeline tests (`tests/unit/renderer/test_libreoffice_pipeline.py`)
- AT-10 render checks tests (`tests/unit/renderer/test_render_checks.py`)
- AT-4 Pydantic codegen tests (`test_pydantic_codegen.py`)
- AT-5 TypeScript codegen tests (`test_typescript_codegen.py`)
- AT-6 schema consumer tests (`test_schema_consumer.py`)

## AT-4 ù Pydantic generation

From repo root:

```bash
py -3 scripts/generate_pydantic.py
```

Produces importable Pydantic v2 models in `generated/python/contracts/` for:
- `framework_object.schema.json`
- `presentation_plan.schema.json`
- `slide_spec/base.schema.json`

Never edit generated files. Change schemas in this directory, then re-run codegen.

## AT-5 ù TypeScript generation

From repo root:

```bash
node scripts/generate_typescript.js
# or: npm run generate:typescript
```

Produces importable TypeScript types in `generated/typescript/contracts/` for:
- `framework_object.schema.json` (includes patched 14-chapter tuple for `chapters`)
- `presentation_plan.schema.json`
- `slide_spec/base.schema.json`

The renderer service imports these via `apps/renderer/src/contracts.ts`. Never edit generated files.

## AT-6 ù schema_version + additive fields

Forward-compatible consumers for canonical contracts (technical plan section 7, AT-6 backlog):

```python
from packages.contracts.schema_consumer import (
    SchemaVersionMismatchError,
    consume_framework_object,
    consume_presentation_plan,
    consume_slide_spec_base,
)
```

Behavior:
- **Unrecognized additive root fields** on `FrameworkObject` / `PresentationPlan` are stripped and ignored.
- **Layout-specific SlideSpec fields** (e.g. `components`) are preserved; unknown additive fields do not fail parsing.
- **Unsupported `schema_version` or missing required v1.0 fields** raise `SchemaVersionMismatchError` with a clear version-mismatch message.

## Rules

- Edit schemas here only ù never hand-edit `generated/`.
- `chapter_registry.json` must stay aligned with `framework_object.schema.json` chapter prefixItems.
- `layout_registry.json` must stay aligned with `LayoutId` enums in `presentation_plan.schema.json` and `slide_spec/base.schema.json`.
- Layout developers: see `slide_spec/README.md` for extending `SlideSpecBase`.
