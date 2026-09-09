# MS-31 — Journey-stage selection on the landing page

Phase 3. Owner: Mayank Somwani. Priority: P0.

The landing page (`apps/web/src/app/page.tsx`, today just
`RecentPresentationsPanel`) becomes where the user chooses which of the three
journey outputs to produce: First contact, Deepening, Concretisation. The
stages are cumulative — a Deepening pitch is only meaningful if a First contact
pack already exists for that client, because it continues from it, and a
Concretisation proposal builds on the Deepening pitch in the same way.

So the later two options are not freely selectable. They stay locked until the
stage before them has actually produced a deck for that client.

## What to deliver

On the landing page, carried through the create-opportunity / upload screen:

- Three named options in business language, with First contact as the default
  for a client with no history.
- Deepening locked until a completed First contact deck exists for that client;
  Concretisation locked until a completed Deepening deck exists.
- A locked option states the reason and the next action ("Generate a First
  contact pack for this client first"), rather than being greyed out in
  silence. It is not clickable and cannot be submitted.
- Eligibility is read from the BT-31 endpoint. The UI does not derive the rule
  itself — two implementations of the same rule will drift.
- The selected stage travels with the opportunity into the Framework and
  Approve flow, so the user chooses once.
- No stage id, template id, engine or vendor name is ever shown.

D2 has not answered whether Deepening survives review. The option set must come
from configuration, so dropping to two stages is a config change and not a
rewrite.

## Done when

A first-time user for a new client sees First contact selectable and the other
two locked with a readable reason. Once a First contact deck exists, Deepening
becomes selectable; once a Deepening deck exists, Concretisation does. No user
can start a stage whose prerequisite is missing, and a client with only one
available option does not look broken.

## Proof

- Unit / UI tests for all three eligibility states, including locked-reason
  copy and the non-submittable locked option.
- Contract test: the component renders backend eligibility and fails if asked
  to compute it locally.
- Isolation: another user's or another client's history does not unlock a stage.
- Selected stage round-trips from landing page through Approve.
- Screenshot: new client, default First contact, two locked options.
- Config with Deepening removed renders two options and still chains correctly.

## Depends on

BT-31 for the eligibility response JSON only — freeze that shape first and this
ticket builds against a fixture instead of waiting. MS-24, MS-27, AT-58, MS-30
(seed data to demonstrate the unlocked states, same owner), JJ-31 (what each
stage actually produces), D2.
