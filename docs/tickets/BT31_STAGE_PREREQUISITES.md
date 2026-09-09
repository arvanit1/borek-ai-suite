# BT-31 — Journey-stage prerequisites and prior-stage context

Phase 4. Owner: Blenard Tahiraj. Priority: P0.

MS-31 shows three journey options with the later two locked. The lock has to be
real: the backend decides which stages a client may start, and refuses the rest
even when the request bypasses the UI. The same mechanism supplies the reason a
later stage exists at all — a Deepening pitch continues the First contact pack,
and a Concretisation proposal continues the Deepening pitch, so each job must
be handed the confirmed content of the stage before it.

## What to deliver

- Stage recorded on the presentation version, so a deck's journey stage and its
  lineage to the earlier stage are queryable.
- An eligibility contract per client / opportunity: which stages are startable,
  and for each blocked one, the machine-readable reason. MS-31 renders this and
  does not recompute it.
- Server-side enforcement: a request to start a locked stage is refused with a
  classified error MS-28 can map to a next action. Never a 500, never a
  partially created job.
- Prior-stage context loading: a Deepening job loads the confirmed First
  contact Framework and its deck version reference and passes them into the
  JJ-31 payload build; Concretisation does the same from Deepening.
- Prerequisite that disappeared (deleted or superseded earlier version) is an
  `INPUT_REQUIRED`-class state, not a crash and not an invented empty context.
- Duplicate clicks, refresh and reconnect must not start two jobs for the same
  stage, and superseding an earlier stage must not silently invalidate the
  decks built on it — record the lineage instead.
- Stage is a business choice and is never coupled to `PRESENTATION_ENGINE`. The
  engine stays invisible (JJ-28).

## Done when

Eligibility returns exactly which stages are startable and why the others are
not. A direct API call for a locked stage is refused cleanly. A Deepening job
demonstrably carries First contact content into its payload. Lineage from a
later deck back to the earlier one is queryable.

## Proof

- Unit tests: no history → only First contact; one First contact deck →
  Deepening unlocked; one Deepening deck → Concretisation unlocked.
- Direct `POST` for a locked stage → classified refusal, no job row created.
- Deepening payload contains identifiable First contact facts (paired with the
  JJ-31 carry-forward test).
- Missing or superseded prerequisite → `INPUT_REQUIRED`-class state with a next
  action, surfaced through MS-28.
- Duplicate Approve / refresh → one job (AT-56 / AT-57 rules unchanged).
- Lineage query returns the earlier version for a later-stage deck.

## Depends on

BT-28 (Gamma stage — same owner), AT-56, AT-57, D2. From JJ-31 it needs the
stage enum and profile block, and from AT-61 the lineage field; freeze both
shapes first so this ticket is not gated on either landing. MS-31 and MS-28 are
consumers, not blockers.
