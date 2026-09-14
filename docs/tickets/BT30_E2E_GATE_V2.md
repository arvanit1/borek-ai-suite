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

## Proof

- Automated E2E (extend `tests/integration/full_pipeline/test_bt27_e2e_gate.py`)
  covering flag on, flag off, and one classified provider failure.
- Manual smoke: optional logo present and absent; reconnect during Gamma.
- Filing metadata present on the archived artifact (AT-61), if O2 is decided;
  otherwise the in-app archive path still records version and provenance.

## Depends on

BT-28, BT-29, AT-58, AT-59, AT-60, AT-61, ES-38, ES-39, ES-40, JJ-26, JJ-28,
MS-27, MS-28. O2 blocks the enterprise-repository part of filing only.
