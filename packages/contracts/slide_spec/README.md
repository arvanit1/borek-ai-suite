# SlideSpec schemas (AT-3+)

Layout-specific SlideSpec JSON Schemas live here. **AT-3** defines only the shared base; each layout group adds its own schema files.

## AT-3: `base.schema.json`

Every layout-specific SlideSpec **extends** `#/$defs/SlideSpecBase` from `base.schema.json`.

### Required base fields

| Field | Description |
|-------|-------------|
| `schema_version` | Always `"1.0"` (section 32) |
| `layoutId` | One of the 15 MVP layouts in `layout_registry.json` |
| `title` | Primary slide heading |
| `sourceChapterIds` | Non-empty list of FrameworkObject chapter ids (`"0"`..`"13"`) |

### Optional base fields (section 14 example)

| Field | Description |
|-------|-------------|
| `slideId` | Stable id within a presentation version |
| `sectionLabel` | Eyebrow label, e.g. `ARCHITECTURE` |
| `subtitle` | Secondary heading when the layout supports it |

Layout-specific fields (e.g. `components`, `phases`, `statBadges`) are **not** in the base schema. Each layout schema adds them via `allOf`.

## How to extend the base (BT / JJ / MS)

Create a layout schema under your group folder, e.g. `group_a/cover_01.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://borek.ai/schemas/slide_spec/cover_01/v1.0",
  "title": "Cover01SlideSpec",
  "allOf": [
    { "$ref": "../base.schema.json#/$defs/SlideSpecBase" },
    {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "layoutId": { "const": "COVER_01" },
        "statBadges": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["label", "value"],
            "properties": {
              "label": { "type": "string" },
              "value": { "type": "string" }
            }
          }
        }
      },
      "required": ["statBadges"]
    }
  ]
}
```

Notes:

1. **Pin `layoutId`** with `"const": "<LAYOUT_ID>"` in the layout-specific `allOf` branch.
2. **`sourceChapterIds` is mandatory** on every variant (section 14). Per-field traceability is enforced in BT-14 / JJ-9 / MS-11, not in the base schema.
3. **Chapter id format** is `"0"`..`"13"` (matches `FrameworkObject.chapters[].chapter_id`), not `chapter_6` (that format is for `PresentationPlan.frameworkReferences` only).
4. Set **`additionalProperties": false`** on the layout branch so only base + layout fields are allowed.

## Fixture

`packages/contracts/fixtures/slide_spec/architecture_01.minimal.json` mirrors the section 14 ARCHITECTURE_01 example and validates against `SlideSpecBase` (layout-specific `components` are allowed via `additionalProperties: true` on the base).

## Validation

From repo root:

```bash
py -3 scripts/validate_all.py
```

Contract tests for AT-3: `tests/unit/contracts/test_slide_spec_base_schema.py`
