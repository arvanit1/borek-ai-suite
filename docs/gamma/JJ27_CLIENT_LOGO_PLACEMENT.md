# JJ-27 — Client logo placement rules

Phase 4.

An uploaded client logo is co-branding, not branding. The Borek logo is part of
the locked template (bottom-left header/footer, every card) and nothing here can
move or replace it. The rules below decide only whether the *client* logo is
placed alongside it.

Machine-readable rules: the `client_logo` block of
[`packages/contracts/gamma_template.json`](../../packages/contracts/gamma_template.json).
Implementation: `apps/api/services/gamma/client_logo.py`.

## Where it appears

| Rule | Value |
| --- | --- |
| Cards | cover and closing only — never on content cards |
| Position | bottom-right of the card |
| Maximum height | 6% of card height, aspect ratio preserved |
| Minimum clear space | 3% of card height on every side |
| Co-branding | always paired with the Borek theme logo bottom-left |

The logo is scaled to fit the box. It is never cropped, never stretched, and
never recoloured.

## Quality gate

The logo is placed only if all of these hold. Dimensions and MIME type come from
the AT-58 upload record, so nothing is re-decoded here.

| Check | Threshold | Reason string when it fails |
| --- | --- | --- |
| Dimensions recorded | width and height present | `dimensions_unknown` |
| Shortest edge | ≥ 128px | `below_minimum_resolution` |
| Total pixels | ≥ 24 576 | `insufficient_pixels` |
| Aspect ratio | ≤ 8:1 | `extreme_aspect_ratio` |

The 128px floor is deliberately stricter than the 64px the upload endpoint
accepts: an image can be a valid upload and still be too coarse to sit next to
the Borek wordmark at print size. `dimensions_unknown` covers logos uploaded
before migration 020 added the width and height columns.

A logo that passes but has no transparency — currently JPEG — is placed on a
white plate so it does not show as a dark rectangle on the dark cover. That case
reports `applied_on_white_plate`.

## When the logo is missing or rejected

There is one fallback for every failure: `client_name_wordmark`. The cover keeps
the client name it already carries in the required `cover.client_name` slot, set
in the template's client-name style, and no image is placed. The deck is still
correct and still co-branded in text; it simply has no client mark.

The pipeline never fails because of a logo. Every outcome is recorded on the
`GAMMA_RENDERING` job result under `client_logo`:

```json
{
  "applied": false,
  "reason": "below_minimum_resolution",
  "detail": "Logo shortest edge is 96px, below the 128px minimum.",
  "fallback": "client_name_wordmark",
  "position": null,
  "cards": [],
  "backdrop": null
}
```

That is what an operator reads to explain why a deck came back without the
client mark, and it is what tells them to ask for a better file.

## Reaching Gamma with the bytes

`client_logo_ref` is an owned storage reference. `artifact:logos/{opportunity}`
and `s3://borek-client-logos/…` are private: Gamma cannot fetch them, so the
live adapter leaves the image out and the deck falls back to the wordmark. That
outcome is reported as `provider_could_not_fetch_reference` rather than being
silently reported as applied.

Only an `https://` reference is actually placed, via the template's bottom-right
header/footer image slot. Issuing a short-lived signed URL for the stored logo
is tracked as [JJ-29](JJ29_SIGNED_LOGO_URL.md); the rules, the gate, and the
payload shape are in place and exercised by the fixture client today.
