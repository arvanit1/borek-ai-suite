# JJ-31 — Stage profiles for the Borek template

Phase 3 design, Phase 4 delivery. Owner: Jaya Joshi. Priority: P0.

[JJ-26](JJ26_BOREK_GAMMA_TEMPLATE.md) defines exactly one template with one
fixed slot set, because at the time there was one output. MS-31 introduces
three journey outputs, and they are not the same deck with different words:

| Stage | What it is | What it must not contain |
| --- | --- | --- |
| First contact | Generic Borek information pack | No prices, no client-specific references, no client logo |
| Deepening | Tailored pitch with references and the client logo | No offer-grade pricing |
| Concretisation | Priced proposal | No price that ES-39 did not ground; nothing unlabelled as indicative |

This ticket makes the slot layer stage-aware without duplicating it three
times.

## What to deliver

Add a `stage_profiles` block to
[`packages/contracts/gamma_template.json`](../../packages/contracts/gamma_template.json)
declaring, per stage: which cards are included, which Framework chapters feed
each slot, the character budgets, and whether pricing chapters are permitted at
all. The JSON stays the source of truth; this document is derived from it.

`apps/api/services/gamma/slot_mapping.py` then builds a payload for a named
stage rather than for the single implicit one:

- An excluded card produces no slot, not an empty slot.
- Chapter 9 (Business case & ROI) stays excluded everywhere except
  Concretisation, and there only for facts carrying ES-39 provenance.
- The client logo slot (JJ-27 / JJ-29) is enabled for Deepening and
  Concretisation only.
- A later stage may reuse the confirmed content of the stage before it, passed
  in by BT-31, so the pitch continues the pack instead of restarting the story.
- An unknown or missing stage is `GAMMA_PAYLOAD_INVALID`, not a silent default.

Every slot a profile newly enables must be classified and allow-listed per
stage in [`config/data_egress_policy.yaml`](../../config/data_egress_policy.yaml),
or the live send fails closed — that closure is BT-32.

D2 has not decided one template with three profiles versus three templates.
Land the profile abstraction so that either answer is configuration: the
profile may carry its own `template_id`.

## Done when

The contract declares three profiles and `slot_mapping` builds a
stage-appropriate payload for each. A First contact payload contains no pricing
and no client logo. A Deepening payload carries references and the logo slot. A
Concretisation payload carries indicative prices only where ES-39 grounded
them, labelled as indicative per D5. Branding stays locked in all three.

## Proof

- Contract test per stage (extend `tests/unit/gamma/test_jj26_template_contract.py`).
- First contact payload asserts absence of chapter 9 and of the logo slot.
- Deepening payload includes the logo slot and reference content.
- Concretisation payload rejects an ungrounded price, and every price present
  carries provenance and the indicative label.
- Carry-forward test: a Deepening payload built with First contact context
  contains identifiable content from it.
- Unknown stage → `GAMMA_PAYLOAD_INVALID`.
- Egress allow-list coverage for each profile's slots.

## Depends on

JJ-26 (slots), ES-40 (payload from Framework and retrieved facts), ES-39
(grounded prices), JJ-29 (logo) — all the same owner, so the whole content
chain sits in one place. From BT-31 it needs only the shape of the prior-stage
context it will be handed; freeze that and build against a fixture. D2 (one
template or three), D5 (indicative or offer-grade), O1 (formats).
