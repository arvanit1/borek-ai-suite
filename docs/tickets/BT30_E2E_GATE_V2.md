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

## Proof

- Automated E2E (extend `tests/integration/full_pipeline/test_bt27_e2e_gate.py`)
  covering flag on, flag off, and one classified provider failure.
- Manual smoke: optional logo present and absent; reconnect during Gamma.
- Filing metadata present on the archived artifact (AT-61), if O2 is decided;
  otherwise the in-app archive path still records version and provenance.

## Depends on

BT-28, BT-29, AT-58, AT-59, AT-60, AT-61, ES-38, ES-39, ES-40, JJ-26, JJ-28,
MS-27, MS-28. O2 blocks the enterprise-repository part of filing only.
