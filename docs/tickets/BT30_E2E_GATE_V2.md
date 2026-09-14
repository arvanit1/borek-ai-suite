# BT-30 — End-to-end gate, second edition

Phase 5. Owner: Blenard Tahiraj. Priority: P0.

BT-27 accepted the original automated journey. This ticket re-accepts the
full journey after the client pack, retrieval and Gamma are in place, including
failure and recovery.

## What to deliver

A release gate that a clean user can complete without developer intervention:

Login → create presentation → optional logo and client information → upload
transcripts → Framework → review / export → Approve & build presentation →
automatic planning, slides, retrieval, Gamma (or internal fallback) →
preview → download PowerPoint / PDF.

Also cover:

- Fast path with no logo and no extra client fields (MS-27 optional).
- Retrieval miss becomes an open question, not invented pricing (ES-39).
- Gamma failure is understandable and recoverable (MS-28); flag revert uses
  the internal renderer (BT-28).
- English end-to-end pass; German smoke.
- Security, provenance and egress allow-list remain intact (O4).

## Done when

The Phase 5 journey passes on a clean user, including at least one failure path
(Gamma or retrieval) that recovers without a dead end.

## Known live failures (open)

### Duplicate presentation-plan layout IDs (BT-1 / BT-3)

**Observed failure:** Live OpenAI planning could emit duplicate
`PROBLEM_SOLUTION_01` and `PROCESS_FLOW_01` slides when interpreting the
chapter 2 / chapter 4 mapping in `chapter_layout_map.json` as one slide per
chapter per layout. The planner prompt already forbade duplicate layout IDs,
but duplicate-layout validation retries did not pass the failed layout IDs (or
the prior invalid plan) back into the retry context, so three attempts could
repeat the same invalid structure.

**Root cause:**

- BT-1: retry loop incremented `retry_count` only; `planning_input` was unchanged
  on duplicate-layout failures.
- BT-3: multi-chapter mappings did not state clearly enough that layout IDs are
  global slide slots (at most one slide each).

**Fix (2026-09-14):**

- Pass `retryValidationErrors.duplicateLayoutIds`, `forbiddenDuplicateLayoutIds`,
  and `previousInvalidPlan` on duplicate-layout retries.
- Enrich BT-3 guidance with `layoutUniquenessRules` and per-mapping
  `interpretation` text; clarify `chapter_layout_map.json` description and the
  planner prompt.
- Deterministically repair chapter-split duplicates for multi-chapter layout
  slots (chapters 2 and 4 → `PROBLEM_SOLUTION_01` / `PROCESS_FLOW_01`) by
  merging `frameworkReferences` into one slide per layout.

**Live verification (2026-09-14):**

- Path: confirmed Group A framework fixture → live OpenAI `plan_presentation`
- Attempts: 1 (`retry_count` 0)
- Final layout IDs (9 slides, all unique):
  `COVER_01`, `EXECUTIVE_SUMMARY_01`, `CONTEXT_01`, `PROBLEM_SOLUTION_01`,
  `PROCESS_FLOW_01`, `SCOPE_01`, `REQUIREMENTS_MATRIX_01`, `COMPLIANCE_01`,
  `NEXT_STEPS_01`
- `PROBLEM_SOLUTION_01` count: 1
- `PROCESS_FLOW_01` count: 1
- Duplicate layout IDs: none

**Gate status:** Duplicate-layout planner condition **resolved** for live
planning.

### SUCCESS_METRICS_01 commercial content (ES-39 / Group C)

**Observed failure:** Live OpenAI slide generation for `SUCCESS_METRICS_01`
failed during `SLIDE_GENERATING` with
`SUCCESS_METRICS_01 contains prohibited commercial content at $.subtitle`
(`PRESENTATION_CONTINUATION_FAILED`).

**Root cause:**

- Chapter bodies were sanitized before generation, but live LLM output was not
  repaired before ES-39 commercial validation.
- `excludeMonetaryFields=true` applied to the layout mapping but did not reach
  the Group C generator as an explicit exclusion flag or repair step.

**Fix (2026-09-14):**

- Enabled `exclude_monetary_fields` on `SUCCESS_METRICS_01` generation config.
- Added explicit monetary-exclusion instructions to the live generation prompt.
- Added deterministic commercial-content repair before validation using the
  same canonical `_contains_commercial_value` / `_find_commercial_paths` rules.
- Optional fields (`subtitle`, `sectionLabel`) are removed when commercial;
  required fields are sentence-filtered or replaced with grounded non-commercial
  chapter fallback text.

**Live verification (2026-09-14):**

- Path: confirmed Group A framework fixture → live OpenAI planning → live slide
  generation (`.env` live AI + Gamma)
- Planning: PASS (10 unique layout IDs)
- `SUCCESS_METRICS_01`: PASS — non-commercial subtitle and criteria persisted
- Generation stages reached:
  `SLIDE_GENERATING → SLIDE_VALIDATING → GAMMA_RENDERING → ARTIFACT_FILING → PREVIEW_RENDERING`
- Presentation generation job: `COMPLETED`

**Gate status:** Commercial-content slide-generation blocker **resolved** for
live `SUCCESS_METRICS_01`.

### Gamma failure-path recovery (BT-28 / MS-28)

**Observed failure:** Fixture E2E
`test_bt30_classified_gamma_failure_recovers_without_dead_end` reported
`FAILED` with `error.stage = SLIDE_GENERATING` even though Gamma was invoked
and `error.code = GAMMA_TIMEOUT`.

**Root cause:**

- Synchronous in-process continuation (`continue_after_planning` →
  `enqueue_presentation_generate` → `task.run`) correctly failed the real
  generation job at `GAMMA_RENDERING` via the worker.
- BT-25 continuation error handling then created a **second**
  `presentation_generation` job and hard-coded `failed_stage = SLIDE_GENERATING`,
  masking the authoritative Gamma failure and breaking retry/resume discovery.

**Fix (2026-09-14):**

- Skip duplicate continuation failure rows when a generation job is already
  `FAILED` (preserve worker-recorded stage, code, retryability).
- Derive continuation `failed_stage` from the classified exception
  (`GAMMA_*` → `GAMMA_RENDERING`) when a visibility row is still required.

**Test proof:**

- `test_bt30_classified_gamma_failure_recovers_without_dead_end`: PASS — fails
  at `GAMMA_RENDERING`, retryable, retry completes to ready + downloads.
- Full BT-30 integration suite: `6 passed`.

**Gate status:** Gamma failure-path recovery blocker **resolved** in fixture
E2E. BT-30 E2E gate remains **open** until manual smoke / remaining dependency
items pass.

### GAMMA_PAYLOAD_INVALID on first_contact (ES-40 / Gamma boundary)

**Observed failure:** Live manual smoke on opportunity
`df756ac2-3e9f-47e2-91f5-8a64b6ad83bc` reached
`SLIDE_GENERATING → SLIDE_VALIDATING → GAMMA_RENDERING`, then failed with
`GAMMA_PAYLOAD_INVALID`:
`Prices are not permitted in this payload (400). They are not labelled indicative
as a workaround.`

**Root cause:**

- SlideSpecs are validated for commercial content at generation time, but the
  live Gamma payload is built from confirmed Framework chapter prose via
  `build_gamma_content_slots` (ES-40), not from SlideSpecs.
- Chapter 1 business-case rows (for example
  `Investment: ~EUR 22500 build · ~EUR 400/month run cost`) and the cover
  tagline were flattened into `executive_summary.body`, `context.summary`, and
  `cover.subtitle`.
- `refuse_ungrounded_prices(..., allow_prices=False)` correctly refused those
  rate-card-shaped figures on the first_contact profile before HTTP submission.

**Fix (2026-09-14):**

- Added `apps/api/services/gamma/payload_compliance.py`:
  provider-specific repair + `validate_gamma_payload_compliance` immediately
  before Gamma submission.
- Non-pricing stages strip commercial/monetary lines from slot text only;
  optional slots that become empty (for example `cover.subtitle`) are omitted.
- Persisted Framework and SlideSpecs are unchanged.

**Test proof:**

- `tests/unit/gamma/test_gamma_payload_compliance.py` reproduces the manual-smoke
  chapter-1 ROI row and proves compliance repair + local validation.
- Gamma unit suite + BT-30 integration: green.

**Live verification (2026-09-14):**

- Opportunity: `df756ac2-3e9f-47e2-91f5-8a64b6ad83bc`
- Presentation: `e6edf85e-f287-4f9f-9620-5492226fd7e9`
- Job: `981c7746-de22-4947-94e5-06b71f28f866`
- Payload compliance scan: no prohibited paths
- Stages:
  `GAMMA_RENDERING → ARTIFACT_FILING → PREVIEW_RENDERING → COMPLETED`
- Reconnect probe at `GAMMA_RENDERING`: same job ID on refetch (no duplicate)
- Retrieval: deck/preview/PPTX/PDF HTTP 200 (12 slides)

**Gate status:** Gamma payload commercial-content blocker **resolved** for live
first_contact.

### COVER_01 numeric attribution (BT-9 / BT-14, logo-present smoke)

**Observed failure:** Live manual smoke on opportunity
`30a9da97-5798-51fb-bc58-c8028a9124dd` (logo present, `audit-logo.png`
128×128) failed during `SLIDE_GENERATING` with
`COVER_01 contains numeric content at statBadges[0].value absent from its
field-attributed chapters: 95`.

**Root cause:**

- Chapter 1 for this demo service-desk framework has **no numeric tokens** after
  commercial sanitization (monetary KPI rows stripped before Group A generation).
- Live OpenAI still invented `statBadges[0].value = "95"`.
- `wrap_live_structured_generator` can exhaust retries and return the last
  payload; `generate_group_a_slide_spec` then re-validated without a
  deterministic COVER_01 repair step, so strict BT-14 numeric grounding raised
  `UngroundedContentError`.

**Fix (2026-09-14):**

- Added `repair_cover_ungrounded_stat_badges` in
  `apps/api/services/slides/content_generation/group_a/cover_01.py`, wired via
  `GroupAGenerationConfig.pre_validate_repair` before final validation.
- Ungrounded stat-badge values are **dropped** (never spelled out as words to
  evade numeric grounding); provenance is reindexed for retained badges.
- If every badge is unsupported numeric, repair leaves no fabricated
  replacement and BT-15 `min_items` / bounded regeneration fail closed.
- Validator strictness unchanged; no invented source refs or replacement stats.

**Test proof:**

- New COVER_01 regression tests in
  `tests/unit/slides/test_group_a_content_generation.py` (ungrounded `95`,
  grounded `80%`, drop-unrepairable badge, non-numeric unchanged, valid spec
  unchanged).
- BT-30 integration gate: `6 passed`.

**Live verification — grounding safety (2026-09-14, PR #106 merged):**

- Opportunity: `30a9da97-5798-51fb-bc58-c8028a9124dd`
- Logo: persisted (`audit-logo.png`, 128×128)
- Direct live OpenAI `generate_cover_01` on confirmed framework: **VALIDATION_FAILED**
  — all LLM stat badges were unsupported numeric/spelled claims and were
  dropped; BT-15 `min_items=1` fail-closed (no word-form evasion, no fabricated
  replacement badges)

**Follow-up fix — BT-15 `min_items=1` when no grounded numbers (2026-09-14):**

- Chapter 1 source for this opportunity: title `Management summary`, empty body,
  **no numeric tokens** after commercial sanitization.
- Prompt now requires at least one statBadge; prefers grounded numeric only when
  present in source; otherwise a short non-numeric badge from chapter title/body.
- When repair drops all unsupported numeric badges, `_deterministic_grounded_non_numeric_badge`
  extracts the longest verbatim source word (≤16 chars) plus a grounded label from
  the same chapter text; bounded retry adds explicit non-numeric instructions when
  `min_items` still fails.
- Numeric grounding and BT-15 strictness unchanged; no generic hard-coded fallbacks
  (`Trusted`, `Reliable`, etc.).

**Live verification — minItems fix (2026-09-14):**

- Direct live `generate_cover_01` on opp `30a9da97`: **VALID**
  - `statBadges`: `[{ "value": "Overview", "label": "Chapter Focus" }]`
  - No invented numeric claims (`95`, `ninety-five`, etc.)
  - `fieldProvenance` valid for chapter `1`
- Logo-present full pipeline job `c60a5c6d-dbc4-4992-831a-2e94ef06b920`:
  **COMPLETED** (12 slides, Gamma PPTX/PDF filed)
- Visual logo verification on rendered deck: **not performed** in this run

**Gate status:** COVER_01 **minItems blocker resolved** for the logo-present
opportunity (live COVER VALID; full deck generation COMPLETED). Logo-present
manual smoke remains **partially open** until rendered preview/PPTX is fetched
and the client logo is visually confirmed on COVER. Remaining blockers: German
live path and UI reconnect success-path proof.

## Proof

- Automated E2E (extend `tests/integration/full_pipeline/test_bt27_e2e_gate.py`)
  covering flag on, flag off, and one classified provider failure.
- Manual smoke: optional logo present and absent; reconnect during Gamma.
- Filing metadata present on the archived artifact (AT-61), if O2 is decided;
  otherwise the in-app archive path still records version and provenance.

## Depends on

BT-28, BT-29, AT-58, AT-59, AT-60, AT-61, ES-38, ES-39, ES-40, JJ-26, JJ-28,
MS-27, MS-28. O2 blocks the enterprise-repository part of filing only.
