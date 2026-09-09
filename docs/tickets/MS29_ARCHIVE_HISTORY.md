# MS-29 — Archive and history view

Phase 5. Owner: Mayank Somwani. Priority: P2.

MS-24 lists recent presentations. This ticket extends that into a view over
filed collateral so past decks can be found and reused once automatic filing
exists.

## What to deliver

A history / archive view built on AT-61 filing metadata:

- Same customer-facing statuses as MS-24 where they still apply, plus a clear
  Filed / Archived state.
- Find by client, date, opportunity name — not by UUID.
- Open, download PowerPoint / PDF, and (where allowed) resume.
- User isolation; empty state.
- Do not expose storage keys, Gamma ids, or engine names.

Until O2 names the enterprise repository, the view reads Pitch Factory’s own
filed artifacts. Connecting to SharePoint (or equivalent) is out of scope
until that decision lands.

## Done when

A returning user finds a previously generated deck from the archive without
knowing the opportunity UUID, and can download it. Filing that has not
happened yet shows a clear empty or “not filed” state rather than a dead end.

## Proof

- List isolation: user B does not see user A’s filed artifacts.
- Download from archive matches the ready-screen files (JJ-28).
- Empty state with no filed work.
- Blocked-on-O2 path: UI copy does not claim an external repository that is not
  connected.

## Depends on

MS-24, AT-61, O2 (enterprise destination). AT-61 can ship in-app filing
before O2; this UI must degrade honestly until then.
