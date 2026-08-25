# Borek AI Suite — Implementation Status (AT-1 through AT-14)

**Purpose:** Give any AI assistant or developer **full context** on what has been built, where it lives, how it is tested, and what remains. This document reflects the repo as of **August 2026**, branch **`arvanit`**, after local completion of **AT-13** and **AT-14**.

**Delivery gate (must pass before marking tickets done):**

```bash
py -3 scripts/validate_all.py
```

Last verified gate: **192 pytest tests passed**, renderer `test:at9`–`test:at14` passed, codegen + typecheck passed → **ALL CHECKS PASSED**.

---

## Table of contents

1. [Project overview](#1-project-overview)
2. [What is done vs pending (git reality)](#2-what-is-done-vs-pending-git-reality)
3. [Architecture and stack](#3-architecture-and-stack)
4. [Repository map (implemented areas)](#4-repository-map-implemented-areas)
5. [Ticket-by-ticket implementation log](#5-ticket-by-ticket-implementation-log)
6. [Related work by other developers (on main)](#6-related-work-by-other-developers-on-main)
7. [Test inventory](#7-test-inventory)
8. [Design system reference (AT-11–14)](#8-design-system-reference-at-1114)
9. [Validation pipeline reference (AT-7–10)](#9-validation-pipeline-reference-at-710)
10. [Codegen and contract consumption (AT-4–6)](#10-codegen-and-contract-consumption-at-46)
11. [Conventions and rules](#11-conventions-and-rules)
12. [What is NOT implemented yet](#12-what-is-not-implemented-yet)
13. [Onboarding checklist for Claude / new developers](#13-onboarding-checklist-for-claude--new-developers)

---

## 1. Project overview

**Borek AI Suite** (repo name: **borek-ai-suite**) is the **Framework & Presentation Generation Pipeline** for Borek Solutions sales engineering.

| Input | Output |
|-------|--------|
| Meeting transcript(s) from discovery calls | **Framework Object** — 14-chapter structured automation proposal |
| Human-confirmed Framework Object | **Presentation Plan** — ordered slides with layout IDs |
| Approved Presentation Plan + SlideSpecs | Branded **`.pptx`** deck (+ PDF/PNG previews) |

**Core principle:** The **Framework Object** is the single structured artifact. The deck is generated **only** from human-confirmed framework content, never re-parsed from raw transcripts.

**Arvanit Telaku's slice (AT tickets):** platform spine — JSON Schema contracts, codegen, generic validation, renderer design system, preview pipeline. **Not** AI prompting (Endrit), **not** individual slide layouts (Blenard/Jaya/Mayank), **not** web UI yet (AT-46+).

Ownership boundaries: `docs/SCOPE.md`.

---

## 2. What is done vs pending (git reality)

### Merged on `main` (via PRs)

| PR | Commit area | Tickets |
|----|-------------|---------|
| #1 | Schema bootstrap | Step 0, **AT-1, AT-2, AT-3** |
| #2 | Codegen + consumers | **AT-4, AT-5, AT-6** |
| #3 | Validation + preview | **AT-7, AT-8, AT-9** |
| #5 | Group A SlideSpec schemas (Blenard) | **BT-4..BT-8** |
| #6 | Render checks + design tokens | **AT-10, AT-11, AT-12** |

Current `main` HEAD (after #6 merge): `299966d`.

### Implemented locally on `arvanit` (not yet committed at time of writing)

| Ticket | Summary | Key paths |
|--------|---------|-----------|
| **AT-13** | Spacing/grid tokens | `apps/renderer/design_system/tokens/spacing.ts` |
| **AT-14** | `MASTER_DEFAULT` slide master | `apps/renderer/design_system/masters/MASTER_DEFAULT.ts` |

Also local: `pptxgenjs` dependency, `test:at13`/`test:at14`, `validate_all.py` updated to AT-14.

**Commit rhythm (team agreement):** batch commits every **3 tickets**. Next batch should include **AT-11 + AT-12 + AT-13** (AT-11/12 already on main via PR #6; AT-13 still needs commit). AT-14 will follow in the next batch with AT-15/16.

---

## 3. Architecture and stack

Aligned to **Technical Plan v2 §4** and **Development Task Backlog v1.0**.

| Layer | Technology | Owner tickets | Status |
|-------|------------|---------------|--------|
| Contract SSOT | JSON Schema Draft 2020-12 | AT-1..3 | Done |
| Python models | Pydantic v2 (codegen) | AT-4 | Done |
| TypeScript types | json-schema-to-typescript + patches | AT-5 | Done |
| Contract consumers | Python strip additive fields | AT-6 | Done |
| SlideSpec constraints | Python config-driven validator | AT-7 | Done |
| Compression retry | Python orchestration | AT-8 | Done |
| Preview pipeline | Node + LibreOffice + poppler | AT-9 | Done |
| Render validation | Node + pngjs | AT-10 | Done |
| Design tokens | Node + TypeScript | AT-11..13 | Done (13 local) |
| Slide masters | Node + **PptxGenJS** | AT-14 | Done (local) |
| PPTX rendering | Node + PptxGenJS | AT-15+ | Not started |
| API / worker / web | FastAPI, Celery, Next.js | AT-34+ | Not started |

**Important split:** Python owns **API validation**; Node/TypeScript owns **PPTX generation and preview**.

---

## 4. Repository map (implemented areas)

```
borek-ai-suite/
├── packages/contracts/          # AT-1..3 SSOT — JSON Schemas + registries
├── scripts/
│   ├── generate_pydantic.py       # AT-4
│   ├── generate_typescript.js   # AT-5
│   ├── validate_all.py          # Delivery gate (AT-1..14)
│   └── docker/at9-e2e/          # Docker E2E for LibreOffice tests
├── generated/                     # Codegen output — DO NOT hand-edit
│   ├── python/contracts/
│   └── typescript/contracts/
├── apps/
│   ├── api/services/validation/ # AT-7, AT-8
│   ├── worker/tasks/            # AT-9, AT-10 CLI wrappers
│   └── renderer/
│       ├── src/contracts.ts       # Re-exports AT-5 types
│       ├── validation/            # AT-9, AT-10
│       ├── design_system/
│       │   ├── tokens/            # AT-11, AT-12, AT-13
│       │   └── masters/           # AT-14
│       └── scripts/               # CLI entrypoints for worker
└── tests/unit/                    # Pytest wrappers + contract tests
```

**Intentionally empty (placeholders):** `apps/renderer/layouts/`, `apps/renderer/design_system/components/`, `apps/web/`, most of `apps/api/routes/`.

---

## 5. Ticket-by-ticket implementation log

### AT-1 — Define FrameworkObject schema

**Backlog done-when:** Canonical JSON Schema for the 14-chapter Framework Object exists and validates fixtures.

| Item | Detail |
|------|--------|
| **File** | `packages/contracts/framework_object.schema.json` |
| **Registry** | `packages/contracts/chapter_registry.json` — 14 chapters, ids `"0"`–`"13"`, fixed titles from technical plan §8 |
| **Version** | `schema_version: "1.0"` |
| **Key fields** | `opportunity_id`, `title`, `department`, `status`, `priority_rank`, `quality_scores`, `kpis`, `systems`, `rules`, `exceptions`, `access_needs`, `evolution_stages`, `open_items`, `chapters` (tuple of 14), versioning metadata |
| **Chapters** | `prefixItems` tuple — each chapter has fixed `chapter_id` + `title`; content blocks vary by chapter |
| **Fixtures** | `packages/contracts/fixtures/framework_object.minimal.json` |
| **Tests** | `tests/unit/contracts/test_framework_object_schema.py` (11 tests) |
| **Depends on** | None |

---

### AT-2 — Define PresentationPlan schema

**Backlog done-when:** Schema for ordered slide plan from confirmed Framework Object.

| Item | Detail |
|------|--------|
| **File** | `packages/contracts/presentation_plan.schema.json` |
| **Version** | `schema_version: "1.0"` |
| **Required** | `schema_version`, `title`, `slides` |
| **PlannedSlide** | `order`, `purpose`, `layoutId`, `frameworkRefs`, optional `sectionLabel` |
| **LayoutId enum** | 15 layouts — must match `layout_registry.json` |
| **Fixtures** | `packages/contracts/fixtures/presentation_plan.minimal.json` |
| **Tests** | `tests/unit/contracts/test_presentation_plan_schema.py` (15 tests) |
| **Depends on** | AT-1 (framework refs) |

---

### AT-3 — Define SlideSpec base schema

**Backlog done-when:** Shared SlideSpec fields every layout-specific schema extends.

| Item | Detail |
|------|--------|
| **File** | `packages/contracts/slide_spec/base.schema.json` |
| **Required** | `schema_version`, `layoutId`, `title`, `sourceChapterIds` |
| **Traceability** | `sourceChapterIds` — mandatory link back to FrameworkObject chapters |
| **Optional** | `slideId`, `sectionLabel`, `subtitle` |
| **LayoutId** | Same 15-value enum as PresentationPlan |
| **Fixtures** | `packages/contracts/fixtures/slide_spec/architecture_01.minimal.json` |
| **Tests** | `tests/unit/contracts/test_slide_spec_base_schema.py` (14 tests) |
| **SSOT checks** | `tests/unit/contracts/test_contract_ssot.py` — registry ↔ schema alignment |
| **Depends on** | AT-1, AT-2 |

---

### AT-4 — Generate Pydantic models from schemas

**Backlog done-when:** Python codegen produces importable Pydantic v2 models; never hand-edit output.

| Item | Detail |
|------|--------|
| **Script** | `scripts/generate_pydantic.py` |
| **Tool** | `datamodel-code-generator` → Pydantic v2 `BaseModel` |
| **Output** | `generated/python/contracts/*.py` |
| **Schemas generated** | `framework_object`, `presentation_plan`, `slide_spec_base`, plus 5 Group A layout schemas (BT-4..8) |
| **Tests** | `tests/unit/contracts/test_pydantic_codegen.py` (13 tests) |
| **Depends on** | AT-1, AT-2, AT-3 |

---

### AT-5 — Generate TypeScript types from schemas

**Backlog done-when:** Renderer imports generated TS types; typecheck passes.

| Item | Detail |
|------|--------|
| **Script** | `scripts/generate_typescript.js` |
| **Tool** | `json-schema-to-typescript` + **manual patch** for `FrameworkObject.chapters` tuple |
| **Patch reason** | Generator emits `never[]` for `prefixItems`; patch uses `chapter_registry.json` to emit `ChapterAtIndex0..13` tuple |
| **Output** | `generated/typescript/contracts/*.ts` + `index.ts` barrel |
| **Renderer import** | `apps/renderer/src/contracts.ts` re-exports `FrameworkObject`, `PresentationPlan`, `SlideSpecBase`, `LayoutId`, etc. |
| **Tests** | `tests/unit/contracts/test_typescript_codegen.py` (7 tests) — includes fixture typecheck |
| **Depends on** | AT-1, AT-2, AT-3 |

---

### AT-6 — Schema version + additive field handling

**Backlog done-when:** Forward-compatible consumers strip unknown additive root fields; reject wrong/missing `schema_version`.

| Item | Detail |
|------|--------|
| **File** | `packages/contracts/schema_consumer.py` |
| **Exports** | `consume_framework_object()`, `consume_presentation_plan()`, `consume_slide_spec_base()` |
| **Error** | `SchemaVersionMismatchError` with clear message |
| **Behavior** | Unknown additive **root** fields stripped; layout-specific SlideSpec fields (e.g. future `components`) preserved; wrong version → error |
| **Tests** | `tests/unit/contracts/test_schema_consumer.py` (10 tests) |
| **Depends on** | AT-4 |

---

### AT-7 — Generic SlideSpec constraint validator

**Backlog done-when:** Config-driven validator — no layout-specific `if layoutId ==` branches in core code.

| Item | Detail |
|------|--------|
| **File** | `apps/api/services/validation/constraint_validator.py` |
| **Registry** | `LayoutConstraintRegistry` — layout devs register per-layout JSON configs (BT-15, JJ-10, MS-12) |
| **Violation codes** | `missing_required`, `max_length`, `min_items`, `max_items`, `invalid_type`, etc. |
| **API** | `validate_slide_spec()`, `collect_violations()` → `ConstraintViolation` list |
| **Config shape** | `{ "properties": { "fieldName": { "required": true, "type": "string", "maxLength": 80, ... } } }` |
| **Tests** | `tests/unit/validation/test_constraint_validator.py` (10 tests) |
| **Depends on** | AT-3 |

**Unlocked for:** Blenard/Jaya/Mayank constraint configs; Endrit ES-31.

---

### AT-8 — Compression / retry orchestration

**Backlog done-when:** Up to 2 AI shortening passes on compressible violations; never silently truncate; `sourceChapterIds` immutable.

| Item | Detail |
|------|--------|
| **File** | `apps/api/services/validation/compression_retry.py` |
| **Entry** | `validate_and_compress_slide_spec(slide_spec, registry=, compress=)` |
| **Max attempts** | `MAX_COMPRESSION_ATTEMPTS = 2` |
| **Compressible** | Only violations with code `max_length` |
| **Non-compressible** | Fails immediately (e.g. missing required, wrong array count) |
| **Preserves** | `sourceChapterIds` — compression that changes them → `VALIDATION_FAILED` |
| **Result** | `CompressionResult` with `status`: `VALID` \| `VALIDATION_FAILED`, `compression_attempts`, `error_code` |
| **Helper** | `get_value_at_path()` for dotted/array field paths |
| **Worker stub** | `apps/worker/tasks/slide_compress.py` (placeholder for Celery wiring) |
| **Tests** | `tests/unit/validation/test_compression_retry.py` (14 tests) |
| **Depends on** | AT-7 |

---

### AT-9 — LibreOffice preview pipeline

**Backlog done-when:** `.pptx` → `.pdf` + per-slide `.png` via headless LibreOffice + poppler.

| Item | Detail |
|------|--------|
| **File** | `apps/renderer/validation/libreoffice_pipeline.ts` |
| **Flow** | `soffice --headless --convert-to pdf` → `pdftoppm -png` → normalize to `slide-01.png`, `slide-02.png`, … |
| **Exports** | `runLibreOfficePreviewPipeline()`, `normalizeSlideImagePaths()`, `LibreOfficePipelineError` |
| **CLI** | `apps/renderer/scripts/run_preview_pipeline.ts` |
| **Worker** | `apps/worker/tasks/preview_render.py` → invokes CLI via `npx tsx` |
| **Env vars** | `SOFFICE_PATH`, `LIBREOFFICE_PATH`, `PDFTOPPM_PATH` |
| **Docker E2E** | `scripts/docker/at9-e2e/Dockerfile` — Node 20 + LibreOffice + poppler; used when LO not installed locally |
| **Tests** | `apps/renderer/validation/libreoffice_pipeline.test.ts` + `tests/unit/renderer/test_libreoffice_pipeline.py` (6 pytest) |
| **Depends on** | None (renderer infra) |

**Production note:** AT-50 Docker renderer image should include **poppler-utils** alongside LibreOffice.

---

### AT-10 — Render validation checks

**Backlog done-when:** After preview, validate slide count vs plan, detect blank slides, surface render exceptions.

| Item | Detail |
|------|--------|
| **File** | `apps/renderer/validation/render_checks.ts` |
| **Entry** | `runRenderChecks({ presentationPlan, preview, renderError? })` |
| **Issue codes** | `RENDER_EXCEPTION`, `SLIDE_COUNT_MISMATCH`, `MISSING_SLIDE`, `BLANK_SLIDE`, `INVALID_PREVIEW_ARTIFACT` |
| **Blank detection** | `BLANK_SLIDE_MIN_NON_WHITE_RATIO = 0.001` via pngjs pixel scan |
| **Error code** | `RENDER_VALIDATION_FAILED` |
| **CLI** | `apps/renderer/scripts/run_render_checks.ts` |
| **Worker** | `apps/worker/tasks/render_validate.py` |
| **Docker E2E** | Chains AT-9 → AT-10; mounts **preview artifacts only** (not full repo — Windows `node_modules` breaks Linux esbuild) |
| **Tests** | `apps/renderer/validation/render_checks.test.ts` + `tests/unit/renderer/test_render_checks.py` (5 pytest) |
| **Depends on** | AT-9 |

---

### AT-11 — Define color tokens

**Backlog done-when:** One file holds every brand color; no hardcoded hex in layouts/design_system (except canonical file).

| Item | Detail |
|------|--------|
| **File** | `apps/renderer/design_system/tokens/colors.ts` |
| **Source** | Technical plan v2 §16 `BorekTheme.colors` |
| **Tokens** | See [Design system reference](#8-design-system-reference-at-1114) |
| **Convention** | Hex **without** `#` (PptxGenJS) |
| **CI guard** | `colors.test.ts` scans `layouts/` + `design_system/` for hardcoded hex |
| **Tests** | `colors.test.ts` + `tests/unit/renderer/test_color_tokens.py` |
| **Depends on** | None |

---

### AT-12 — Define typography tokens

**Backlog done-when:** Heading/body font families and default sizes centralized; not redefined per layout.

| Item | Detail |
|------|--------|
| **File** | `apps/renderer/design_system/tokens/typography.ts` |
| **Fonts (§16)** | `heading`: `"Aptos Display"`, `body`: `"Aptos"` |
| **Default sizes** | `heading`: 28 pt, `body`: 12 pt — named tokens; exact pts calibrate in AT-55 golden tests |
| **CI guard** | Scans for inline `"Aptos"`, `"Aptos Display"`, `fontSize:` literals |
| **Tests** | `typography.test.ts` + `tests/unit/renderer/test_typography_tokens.py` |
| **Depends on** | None |

---

### AT-13 — Define spacing/grid tokens

**Backlog done-when:** Margins, footer height, grid spacing centralized and referenced by name.

| Item | Detail |
|------|--------|
| **File** | `apps/renderer/design_system/tokens/spacing.ts` |
| **Spacing (§16, inches)** | `marginX: 0.65`, `marginTop: 0.5`, `footerHeight: 0.35` |
| **Grid (derived)** | `columnGap = marginX/2`, `rowGap = marginTop/2` — no orphan literals |
| **CI guard** | Scans for inline `marginX:`, `footerHeight:`, etc. |
| **Tests** | `spacing.test.ts` + `tests/unit/renderer/test_spacing_tokens.py` |
| **Git status** | **Local only** (not on main at time of writing) |
| **Depends on** | None |

---

### AT-14 — Build MASTER_DEFAULT

**Backlog done-when:** Base SlideMaster with **logo**, **footer**, and **page-number placeholders**, positioned per design tokens.

| Item | Detail |
|------|--------|
| **File** | `apps/renderer/design_system/masters/MASTER_DEFAULT.ts` |
| **Dependency added** | `pptxgenjs@^3.12.0` (first PptxGenJS rendering ticket) |
| **Exports** | `MASTER_DEFAULT_NAME`, `MASTER_DEFAULT_LOGO_PLACEHOLDER` (`"logo"`), `MASTER_DEFAULT_FOOTER_PLACEHOLDER` (`"footer"`), `BorekSlide`, `computeMasterDefaultLayout()`, `registerMasterDefault(pptx)` |
| **Slide size** | `LAYOUT_WIDE` — 13.333" × 7.5" (§16) |
| **Layout math** | All positions from `BorekSpacing`; colors from `BorekColors`; fonts from `BorekTypography` |
| **Logo region** | Top-left: `(marginX, marginTop)`, size `(marginX×2, footerHeight)` |
| **Footer region** | Body placeholder in footer band at `y = 7.5 - footerHeight` |
| **Page number** | Right-aligned in footer band via `slideNumber` config |
| **PptxGenJS note** | Library does not fully emit `pic`-type master placeholders; logo registers as generic placeholder region (`idx="100"` in layout XML). Runtime targeting uses `{ placeholder: 'logo' }`. |
| **Tests** | `MASTER_DEFAULT.test.ts` — layout math + unzip pptx, verify `slideLayout` named `MASTER_DEFAULT` contains body + sldNum placeholders and token-derived EMU positions |
| **Pytest** | `tests/unit/renderer/test_master_default.py` |
| **Git status** | **Local only** |
| **Depends on** | AT-11, AT-12, AT-13 |

**Not in AT-14 scope:** `MASTER_COVER`, `MASTER_SECTION`, `MASTER_CONTENT`, `MASTER_CLOSING` (AT-15–18), `addFooter()` component (AT-21), layout render functions.

---

## 6. Related work by other developers (on main)

These are **not AT tickets** but affect codegen and tests on `main`:

### BT-4 through BT-8 — Group A SlideSpec schemas (Blenard Tahiraj)

Merged via **PR #5** (`7682e4f`).

| Layout ID | Schema file |
|-----------|-------------|
| `COVER_01` | `packages/contracts/slide_spec/group_a/cover_01.schema.json` |
| `CONTEXT_01` | `.../context_01.schema.json` |
| `PROBLEM_SOLUTION_01` | `.../problem_solution_01.schema.json` |
| `SCOPE_01` | `.../scope_01.schema.json` |
| `REQUIREMENTS_MATRIX_01` | `.../requirements_matrix_01.schema.json` |

- Fixtures: `packages/contracts/fixtures/slide_spec/group_a/*.minimal.json` and `*.realistic.json`
- Tests: `tests/unit/contracts/test_group_a_slide_spec_schemas.py` (13 parametrized tests)
- Codegen: included in AT-4/AT-5 schema lists → 8 total generated modules each

**Still pending from Blenard:** BT-15 constraint configs, BT-17..21 layout render functions.

---

## 7. Test inventory

### Delivery gate sequence (`scripts/validate_all.py`)

1. `pytest tests/unit -v` — **192 tests**
2. `scripts/generate_pydantic.py`
3. `scripts/generate_typescript.js`
4. Python import smoke test (8 generated modules)
5. TypeScript output file existence check (8 `.ts` files)
6. `npm run typecheck --workspace borek-renderer`
7. `npm run test:at9` through `test:at14`

### Pytest breakdown by area

| Test file | Count | Tickets |
|-----------|-------|---------|
| `test_contract_ssot.py` | 7 | AT-1..3 alignment |
| `test_framework_object_schema.py` | 11 | AT-1 |
| `test_presentation_plan_schema.py` | 15 | AT-2 |
| `test_slide_spec_base_schema.py` | 14 | AT-3 |
| `test_pydantic_codegen.py` | 13 | AT-4 |
| `test_typescript_codegen.py` | 7 | AT-5 |
| `test_schema_consumer.py` | 10 | AT-6 |
| `test_group_a_slide_spec_schemas.py` | 13 | BT-4..8 |
| `test_constraint_validator.py` | 10 | AT-7 |
| `test_compression_retry.py` | 14 | AT-8 |
| `test_libreoffice_pipeline.py` | 6 | AT-9 |
| `test_render_checks.py` | 5 | AT-10 |
| `test_color_tokens.py` | 2 | AT-11 |
| `test_typography_tokens.py` | 2 | AT-12 |
| `test_spacing_tokens.py` | 2 | AT-13 |
| `test_master_default.py` | 2 | AT-14 |

### Renderer npm scripts (`apps/renderer/package.json`)

| Script | Test file |
|--------|-----------|
| `test:at9` | `validation/libreoffice_pipeline.test.ts` |
| `test:at10` | `validation/render_checks.test.ts` |
| `test:at11` | `design_system/tokens/colors.test.ts` |
| `test:at12` | `design_system/tokens/typography.test.ts` |
| `test:at13` | `design_system/tokens/spacing.test.ts` |
| `test:at14` | `design_system/masters/MASTER_DEFAULT.test.ts` |

---

## 8. Design system reference (AT-11–14)

### Colors (`BorekColors`) — AT-11

| Token | Hex (no `#`) | Usage |
|-------|--------------|-------|
| `background` | `FFFFFF` | Slide backgrounds |
| `text` | `182230` | Primary text |
| `mutedText` | `667085` | Footer, secondary |
| `border` | `E4E7EC` | Borders/dividers |
| `primary` | `0057B8` | Brand accent |

### Typography (`BorekTypography`) — AT-12

| Token | Value |
|-------|-------|
| `fonts.heading` | `"Aptos Display"` |
| `fonts.body` | `"Aptos"` |
| `defaultSizes.heading` | `28` pt |
| `defaultSizes.body` | `12` pt |

### Spacing (`BorekSpacing` / `BorekGrid`) — AT-13

| Token | Value (inches) |
|-------|----------------|
| `marginX` | `0.65` |
| `marginTop` | `0.5` |
| `footerHeight` | `0.35` |
| `columnGap` | `0.325` (= marginX/2) |
| `rowGap` | `0.25` (= marginTop/2) |

### Slide master (`MASTER_DEFAULT`) — AT-14

| Constant | Value |
|----------|-------|
| `MASTER_DEFAULT_NAME` | `"MASTER_DEFAULT"` |
| `BorekSlide.widthInches` | `13.333` |
| `BorekSlide.heightInches` | `7.5` |
| Logo placeholder name | `"logo"` |
| Footer placeholder name | `"footer"` |

**Usage pattern for future layouts:**

```typescript
import PptxGenJS from "pptxgenjs";
import { registerMasterDefault, MASTER_DEFAULT_NAME } from "./design_system/masters/MASTER_DEFAULT.js";

const pptx = new PptxGenJS();
registerMasterDefault(pptx);
const slide = pptx.addSlide({ masterName: MASTER_DEFAULT_NAME });
// slide.addText("Footer text", { placeholder: "footer" });
```

---

## 9. Validation pipeline reference (AT-7–10)

### End-to-end preview + validation flow (as implemented)

```
.pptx file
    │
    ▼
[AT-9] runLibreOfficePreviewPipeline()
    ├── stem.pdf
    └── slide-01.png, slide-02.png, ...
    │
    ▼
[AT-10] runRenderChecks(presentationPlan, preview)
    ├── VALID → proceed
    └── VALIDATION_FAILED → RENDER_VALIDATION_FAILED + issues[]
```

### SlideSpec content validation flow (API-side, not yet wired to HTTP)

```
SlideSpec JSON
    │
    ▼
[AT-7] LayoutConstraintRegistry.validate_slide_spec()
    ├── pass → done
    └── max_length violations only
            │
            ▼
        [AT-8] validate_and_compress_slide_spec(compress=AI_fn)
            ├── up to 2 compression passes
            ├── revalidate after each
            └── sourceChapterIds must not change
```

---

## 10. Codegen and contract consumption (AT-4–6)

### Regenerate after any schema change

```bash
py -3 scripts/generate_pydantic.py
node scripts/generate_typescript.js   # or: npm run generate:typescript
npm install                            # once, for renderer workspace
py -3 scripts/validate_all.py
```

### Python consumption

```python
from generated.python.contracts.framework_object import FrameworkObject
from packages.contracts.schema_consumer import consume_framework_object

model = consume_framework_object(raw_dict)  # strips unknown additive root fields
```

### TypeScript consumption

```typescript
import type { PresentationPlan, SlideSpecBase } from "./src/contracts.js";
```

### Layout registry (15 layouts)

From `packages/contracts/layout_registry.json`:

`COVER_01`, `EXECUTIVE_SUMMARY_01`, `CONTEXT_01`, `PROBLEM_SOLUTION_01`, `SCOPE_01`, `REQUIREMENTS_MATRIX_01`, `PROCESS_FLOW_01`, `TIMELINE_01`, `MILESTONES_01`, `TEAM_FTE_01`, `ARCHITECTURE_01`, `COMPLIANCE_01`, `SUCCESS_METRICS_01`, `OPEN_QUESTIONS_01`, `NEXT_STEPS_01`

---

## 11. Conventions and rules

1. **Never hand-edit `generated/`** — change schemas in `packages/contracts/`, rerun codegen.
2. **`chapter_registry.json` ↔ `framework_object.schema.json`** must stay aligned (14 chapters).
3. **`layout_registry.json` ↔ LayoutId enums** in AT-2 and AT-3 must stay aligned.
4. **Design system path** is `design_system/` (underscore), not `design-system/`.
5. **Color hex in renderer** — no `#`; use `BorekColors.*`.
6. **Spacing in renderer** — inches; use `BorekSpacing` / `BorekGrid`.
7. **Typography in renderer** — use `BorekTypography`; guards block inline font families and `fontSize:`.
8. **Ticket ownership** — see `docs/SCOPE.md`; do not implement outside assigned tickets.
9. **Commits** — only when explicitly requested; batch every 3 tickets (team workflow).

---

## 12. What is NOT implemented yet

### Arvanit — immediate next tickets

| Ticket | Summary |
|--------|---------|
| **AT-15** | `MASTER_COVER` |
| **AT-16** | `MASTER_SECTION` |
| **AT-17** | `MASTER_CONTENT` |
| **AT-18** | `MASTER_CLOSING` |
| **AT-19..32** | 14 shared design-system components (`addSlideTitle`, `addFooter`, …) |
| **AT-33** | Layout dispatcher (`layoutId` → render function) |

### Arvanit — platform (after design system)

| Range | Area |
|-------|------|
| AT-34..45 | FastAPI routes, jobs, presentation APIs |
| AT-46..49 | **Next.js UI** (upload, framework review, plan preview, deck center) |
| AT-50..55 | Docker compose, env docs, E2E, golden deck |

### Other developers

| Owner | Pending |
|-------|---------|
| Endrit | ES-* transcript ingestion, knowledge model, framework synthesis |
| Blenard | BT-15 constraints, BT-17..21 Group A renderers |
| Jaya | JJ-* Group B |
| Mayank | MS-* Group C |

### Empty directories (expected)

- `apps/renderer/layouts/group_a/` — `.gitkeep` only
- `apps/renderer/design_system/components/` — `.gitkeep` only
- `apps/web/` — not scaffolded
- `apps/api/routes/` — not implemented

---

## 13. Onboarding checklist for Claude / new developers

When picking up work on this repo, read in this order:

1. **This file** — `docs/IMPLEMENTATION_STATUS.md`
2. **`docs/SCOPE.md`** — who owns what
3. **`README.md`** — full repo map and ticket index
4. **`packages/contracts/README.md`** — schema/codegen rules
5. **`docs/TEAM_HANDOFF_AT7-9.md`** — validation pipeline handoff (partially superseded by this doc)

Before implementing a ticket:

1. Confirm ticket ID and **done-when** from Development Task Backlog
2. Confirm stack from Technical Plan v2 §4/§16
3. Check **depends on** chain in this doc
4. Run `py -3 scripts/validate_all.py` on current branch
5. Implement minimal diff matching existing patterns
6. Add tests + wire into `validate_all.py` if new gate script
7. Re-run full gate

**Current branch:** `arvanit`  
**Remote:** `https://github.com/arvanit1/borek-ai-suite.git`  
**Next recommended ticket:** **AT-15 — Build MASTER_COVER** (after committing AT-13 batch)

---

*Document maintained by the AT implementation workstream. Update this file when completing AT-15+ or when merge status changes.*
