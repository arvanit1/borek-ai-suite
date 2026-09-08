# JJ-28 — One ready screen, whichever engine produced the deck

Phase 4.

A user reaches `/deck-center`, sees "Your presentation is ready", previews the
slides, and downloads the PowerPoint or PDF. Nothing on that path tells them
whether the internal PptxGenJS renderer or Gamma produced the file, and nothing
should.

## What the ready screen serves

`GET /presentations/{id}/deck` returns the same payload either way: slide preview
URLs, `pptx_download_url`, `pdf_download_url`. There is no engine field, and
adding one would be a regression — `tests/unit/api/test_jj28_ready_screen.py`
asserts the payload contains no engine hint.

Downloads resolve through `app/services/deck_center.resolve_deck_file_path`,
which now prefers a Gamma export for the version when one exists:

1. Look for `gamma/{opportunity}/{version}/*.{pptx,pdf}` under the artifact
   root. If found, serve the newest.
2. Otherwise serve the internal render at the version's storage path.

The download URL, the HTTP filename (`{presentation_id}.pptx`) and the content
type are identical in both cases.

## Failures

Gamma errors used to reach the UI verbatim — "Gamma credentials are missing or
rejected." `formatJobFailureMessage` in `apps/web/src/lib/jobErrors.ts` now maps
every `GAMMA_*` code to engine-neutral copy, and `buildJobProgressView` routes
its failure headline through the same function instead of printing the raw
message. Any message that still mentions the provider by name falls back to the
generic "The presentation service could not finish the deck."

The progress stepper already labels `GAMMA_RENDERING` as "Building branded
presentation", and only shows that step once the backend reports it is running,
so a deck built by the internal engine never displays a step it did not take.

## Known gap: previews

Slide previews are PNGs produced from the internal render, which runs before the
Gamma stage. When Gamma produces the download, the previews therefore show the
internal renderer's version of the same content — same slides, same order, same
copy, different visual treatment.

Closing this properly means rasterising the Gamma PDF during
`PREVIEW_RENDERING`. There is no rasteriser in the pipeline yet, so this is
recorded here rather than hidden.
