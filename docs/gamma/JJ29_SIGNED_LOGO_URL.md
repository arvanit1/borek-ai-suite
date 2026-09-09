# JJ-29 — Signed client-logo URL for Gamma

Phase 4. Owner: Jaya Joshi. Priority: P0.

Follow-on from [JJ-27](JJ27_CLIENT_LOGO_PLACEMENT.md). Placement rules, the
quality gate and the payload shape are in place. Gamma still cannot fetch
`artifact:logos/…` or `s3://…` references, so the live adapter leaves the image
out and falls back to the client-name wordmark.

## What to deliver

Issue a short-lived HTTPS URL for a logo that passed the JJ-27 gate, under an
owned host (not an arbitrary `https://` prefix — AT-60 forbids that). Pass
that URL in the template’s bottom-right header/footer image slot. When the URL
cannot be minted, report `provider_could_not_fetch_reference` and keep the
wordmark fallback. The pipeline never fails because of a logo.

## Done when

A quality-gated logo stored by AT-58 is placed on the cover and closing cards
of a live (or owned-host fixture) Gamma deck. A private storage reference is
never sent as-is. Expiry is short. Failure to sign still produces a correct
co-branded deck with the wordmark.

## Proof

- Signed URL minted only after JJ-27 `applied` / `applied_on_white_plate`.
- Arbitrary external HTTPS is still rejected.
- Expired or unsignable ref → `provider_could_not_fetch_reference`, not
  `applied: true`.
- Cover/closing only; Borek mark stays bottom-left.

## Depends on

JJ-27, AT-58, AT-60. Live Gamma access is required to prove placement, not to
land the signer.
