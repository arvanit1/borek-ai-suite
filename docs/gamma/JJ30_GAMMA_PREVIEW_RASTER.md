# JJ-30 — Rasterise Gamma PDF for ready-screen previews

Phase 4. Owner: Jaya Joshi. Priority: P1.

Follow-on from [JJ-28](JJ28_READY_SCREEN_PARITY.md). Downloads already prefer a
Gamma export when one exists. Slide previews are still PNGs from the internal
render, which runs before the Gamma stage. When Gamma produces the download,
the ready screen therefore shows the internal visual treatment of the same
slides.

## What to deliver

Rasterise the Gamma PDF during `PREVIEW_RENDERING` so the ready-screen
preview matches the file the user will download. There is no rasteriser in
the pipeline yet.

Constraints:

- Same slide count and order as the download.
- No engine field on `GET /presentations/{id}/deck`.
- If rasterisation fails, keep the internal previews and still serve the Gamma
  download — never block the ready screen on preview generation.
- Do not name Gamma in the UI.

## Done when

After a Gamma-produced deck, the ready-screen thumbnails match the Gamma PDF
pages (same order, one image per page). An internal-engine deck is unchanged.
A rasteriser failure still shows “Your presentation is ready” with downloads.

## Proof

- Gamma path: preview page count equals PDF page count; images come from the
  Gamma PDF, not the internal PPTX.
- Internal path: existing preview behaviour unchanged.
- Rasteriser crash: downloads still work; payload has no engine hint
  (`tests/unit/api/test_jj28_ready_screen.py` still passes).

## Depends on

JJ-28, BT-28 (Gamma artifact on the version), `PREVIEW_RENDERING` in the
worker.
