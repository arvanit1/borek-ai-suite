# ES-40 — Gamma content payload

Phase 4. Owner: Jaya Joshi. Priority: P0. Carried over. This is the schema
BT-28 builds against.

Build the provider payload from a **confirmed** Framework plus retrieved Borek
facts. Content only — no layout, no styling, no branding keys.

Frozen schema:
[`packages/contracts/gamma_payload.schema.json`](../../packages/contracts/gamma_payload.schema.json)

Fixtures for BT-28:

- [`first_contact.json`](../../packages/contracts/fixtures/gamma_payload/first_contact.json)
- [`deepening.json`](../../packages/contracts/fixtures/gamma_payload/deepening.json)
- [`concretisation.json`](../../packages/contracts/fixtures/gamma_payload/concretisation.json)

`apps/api/services/gamma/payload.py` is the builder. Unknown or missing stages
are `GAMMA_PAYLOAD_INVALID`. First contact and Deepening payloads contain no
pricing facts. Concretisation includes grounded prices with ES-39 provenance and
refuses an ungrounded figure. Chapter 9 still does not fill a JJ-26 slot
(MS-14); JJ-31 maps that chapter onto the Concretisation profile.

## Done when

A payload exists for every stage profile, built from grounded content only, and
the schema is frozen so BT-28 can proceed against the fixtures.
