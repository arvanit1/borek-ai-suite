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
planning. BT-30 E2E gate remains **open** until the full Phase 5 journey
(including Gamma/retrieval failure paths) passes.

## Proof

- Automated E2E (extend `tests/integration/full_pipeline/test_bt27_e2e_gate.py`)
  covering flag on, flag off, and one classified provider failure.
- Manual smoke: optional logo present and absent; reconnect during Gamma.
- Filing metadata present on the archived artifact (AT-61), if O2 is decided;
  otherwise the in-app archive path still records version and provenance.

## Depends on

BT-28, BT-29, AT-58, AT-59, AT-60, AT-61, ES-38, ES-39, ES-40, JJ-26, JJ-28,
MS-27, MS-28. O2 blocks the enterprise-repository part of filing only.
