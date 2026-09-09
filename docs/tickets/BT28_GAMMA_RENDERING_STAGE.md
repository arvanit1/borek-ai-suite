# BT-28 — Gamma rendering stage

Phase 4. Owner: Blenard Tahiraj. Priority: P0.

The internal PptxGenJS render stays in the pipeline as a feature-flagged fallback.
When the presentation engine is Gamma, orchestration must call Gamma as the
deck-producing stage rather than treating it as an optional extra after a
finished internal deck.

## What to deliver

Replace the internal render stage with the Gamma call inside the automatic
pipeline (`Approve & build presentation` → ready screen), behind
`PRESENTATION_ENGINE`. Keep the existing renderer as the fallback until Gamma is
proven in production.

AT-60 already added `JobStage.GAMMA_RENDERING` and
`run_gamma_stage_for_presentation`. This ticket owns the *orchestration* contract:

- The Gamma stage is on the success path when the flag is `gamma`.
- The internal render remains the success path when the flag is `internal`.
- Failure stops at `GAMMA_RENDERING` and preserves earlier work (plan, SlideSpecs,
  Framework). AT-57 resume must restart from this stage, not from planning.
- Duplicate clicks, refresh and reconnect must not enqueue a second Gamma job.
- Generated PPTX/PDF are stored under Borek control (`gamma/{opportunity}/{version}/`).

## Done when

A single Approve action, with `PRESENTATION_ENGINE=gamma`, produces a Gamma
artifact the ready screen can download, without a second user step. Switching
the flag back to `internal` restores the previous renderer path. Users never
choose an engine.

## Proof

- Flag on: Gamma stage runs; owned PPTX/PDF exist; ready-screen download serves
  the Gamma file (JJ-28).
- Flag off: Gamma stage is skipped; internal render is the download.
- Provider failure: job fails at `GAMMA_RENDERING`; Framework and SlideSpecs
  remain; retry resumes from this stage.
- Duplicate Approve / refresh: one job.

## Depends on

AT-60 (adapter, credentials, timeouts, observability), ES-40 (content
payload), JJ-26 (template slots).
