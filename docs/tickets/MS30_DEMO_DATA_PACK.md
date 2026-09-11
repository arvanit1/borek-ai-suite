# MS-30 — Demo data pack: decks, rate cards, client packs, corpus

Phase 3. Owner: Mayank Somwani. Priority: P1.

**Status: closed 11 Sep 2026** for the Mayank deliverable. Seed, production
refusal, ES-39 demo-corpus boundary (unit), live seed-twice, and live SQL RLS
are done. Product-route `borek-demo` opt-in stays Jaya. HTTP two-login pytest
stays optional.

Several tickets cannot be demonstrated because their inputs do not exist yet.
MS-29 needs filed artifacts, MS-31 needs already-generated decks before a later
journey stage can unlock, BT-29 only shows "Retrieving Borek information" when
retrieval is a real stage, and BT-30 needs a failure path it can trigger on
demand. The live sources behind those (AT-59 corpus, AT-61 repository, real
rate cards owned by Fiona) are not landed. This ticket supplies seed data so
the product-facing tickets stop waiting.

This is fixtures, not content authority. ES-39 says the system may never
originate a price, so a demo rate card must be impossible to mistake for a
grounded commercial fact.

## What to deliver

A seeded demo set plus one command to install it:

- Three generated presentations for one demo client, one per journey stage
  (First contact, Deepening, Concretisation), each with PPTX and PDF, so MS-31
  gating and MS-29 archive both have something real to read.
- One versioned demo rate card, in its own corpus id and version — never merged
  into `borek_corpus_v1`.
- Two demo client packs: one rich (logo, all optional fields) and one bare, so
  MS-27's fast path and full path are both visible.
- Demo corpus facts that produce a retrieval hit, a retrieval miss, and an
  ambiguous answer, so MS-28 and BT-30 can trigger each state deliberately.
- `scripts/seed_demo_data.py`: idempotent, scoped to the calling user, gated by
  `DEMO_DATA_ENABLED`, and refusing to run at all under the production runtime
  profile.

Every seeded record carries a `demo` marker, and every surface that shows one
labels it as demo data. A demo artifact must never be reachable from a real
opportunity.

## Done when

A developer with an empty database runs one command and gets a populated
archive, a client whose journey stages unlock in order, and a retrieval stage
that can be made to hit or miss. Running the same command twice changes
nothing. The production profile refuses to seed rather than writing part of it.

## Proof

- Seed twice: identical state, no duplicate rows.
- Production runtime profile: refusal with a clear message, no partial write.
- Demo rate-card facts cite the demo corpus id, and a non-demo opportunity
  cannot retrieve them (ES-39 boundary test).
- RLS: a second user sees none of the first user's demo records.
- MS-29 archive and MS-31 stage selector both render from the seed with no
  hand-editing of the database.

## Depends on

AT-58 (intake persistence), AT-61 (filing metadata shape — same owner, so the
shape is settled in one head), MS-27, MS-29, MS-31. From ES-39 it needs only
the demo corpus id and provenance marker, frozen up front. Real rate cards stay
with AT-59 and Fiona; this ticket never claims to be that source.

## Closed — 11 Sep 2026

| Proof | Evidence |
|---|---|
| Seed twice, no duplicates | `npm run seed:demo` twice on 10 Sep → `2 opportunities, 3 stage decks, 31 records`. Unit: `test_seed_is_idempotent_complete_and_owner_scoped` |
| Production refuses | `test_production_profile_refuses_before_writes` |
| Demo corpus + non-demo cannot retrieve | `test_manifest_uses_frozen_demo_identity_and_valid_retrieval_examples` (`allow_demo=True` hit/miss/ambiguous; blocked without opt-in) |
| RLS second user sees none | Live SQL 10 Sep: owner `b919a044…` sees 2/6/3/3; other uid sees 0 |
| Archive + selector can read the seed | MS-29 `/archive` and MS-31 selector on `main` consume filed artifacts / lineage. No hand-edit of the database |

Re-ran 11 Sep: `py -3 -m pytest tests/unit/api/test_ms30_demo_data.py` plus the MS-30 migration test — 5 passed.

**Not our close gate:** Jaya still owns turning `borek-demo` on in the product retrieval route (MS-28 / BT-29). HTTP two-login pytest is optional (no `RLS_TEST_USER_*`).
