# packages/contracts — Canonical JSON Schemas (SSOT)

Single source of truth for all cross-service data contracts.

| Schema | Ticket | Status |
|--------|--------|--------|
| `framework_object.schema.json` | AT-1 | Complete |
| `presentation_plan.schema.json` | AT-2 | Complete |
| `slide_spec/base.schema.json` | AT-3 | Complete |
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
- Python codegen (AT-4 partial)
- TypeScript codegen (AT-5 partial)

## Rules

- Edit schemas here only — never hand-edit `generated/`.
- `chapter_registry.json` must stay aligned with `framework_object.schema.json` chapter prefixItems.
- `layout_registry.json` must stay aligned with `LayoutId` enums in `presentation_plan.schema.json` and `slide_spec/base.schema.json`.
- Layout developers: see `slide_spec/README.md` for extending `SlideSpecBase`.
