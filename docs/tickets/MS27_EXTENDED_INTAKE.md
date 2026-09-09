# MS-27 — Extended intake experience

Phase 3. Owner: Mayank Somwani. Priority: P0.

The upload / create-opportunity screen is where personalisation is captured.
Both the client logo and the extra client-information fields must read as
genuinely optional so the fast path stays fast.

## What to deliver

On the create-opportunity / upload screen:

- Optional client logo upload with preview, format and size validation, and
  clear errors (PNG, JPEG, WebP; 5 MiB maximum; SVG rejected).
- Optional client information fields: location requirements, constraints,
  contacts, stated priorities, notes.
- Empty state copy that says the user can continue to transcripts with nothing
  filled in.
- Persistence through AT-58 (logo bytes + dimensions, RLS). This ticket is
  the UI; it does not invent a second storage path.

A first implementation already exists (`ClientLogoUpload`,
`OpportunityForm`, `apps/web/src/lib/clientIntake.ts`). Close this ticket only
when the Done when conditions and proofs below are satisfied — including the
live path against AT-58, not only static markup tests.

## Done when

A first-time user can skip logo and extra fields and still start a
presentation. A user who does fill them in sees a preview, validation errors
when the file is wrong, and those values stored on the opportunity. Neither
control is required to proceed.

## Proof

- `npm run` MS-27 unit/UI tests (logo accept/reject, compact empty fields).
- Live: upload a valid logo; reject oversize / SVG; omit logo; fields round-trip
  through AT-58; second user cannot read the first user’s logo (RLS).
- Fast-path screenshot or test: Create opportunity with empty optional section.

## Depends on

AT-58 (intake API, storage, validation, migrations, RLS).
