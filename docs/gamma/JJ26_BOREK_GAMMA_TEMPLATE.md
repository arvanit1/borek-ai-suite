# JJ-26 — The Borek Gamma template and its content slots

Phase 2 design, Phase 4 delivery.

There is exactly one Borek Gamma template. Branding lives inside it and is never
part of a generation request; only the named content slots below vary per
client. This is the concrete form of the O5 "design agent driven by a CI sheet"
decision: the CI sheet is baked into the template once, and the pipeline is
reduced to filling named slots.

Machine-readable contract:
[`packages/contracts/gamma_template.json`](../../packages/contracts/gamma_template.json).
Everything in this document is derived from that file, which is what the code
reads. If the two disagree, the JSON wins and this document is stale.

## Template identity

| Field | Value | Where it lives |
| --- | --- | --- |
| Pitch Factory template id | `borek-branded-standard` | `template_id` in the contract |
| Template version | `v1` | `template_version` in the contract |
| Gamma theme | `GAMMA_THEME_ID` (default `4kv51cbpy4xonmj`, "Borek Pitch Theme") | environment |
| Gamma template/gamma id | `GAMMA_TEMPLATE_ID` | environment |

The Pitch Factory id is what the request carries and what the fixture and live
clients both validate. The Gamma-side ids are deployment configuration so the
same code can point at a staging workspace.

## CI sheet

The CI sheet is applied once, by hand, when the template is built in Gamma. It
is not a runtime input and the pipeline has no way to override it.

| Element | Value |
| --- | --- |
| Primary | `#2C567A` |
| Heading | `#0D1D51` |
| Accent | `#0072C7` |
| Body and heading typeface | Inter |
| Borek logo | theme logo, bottom-left header/footer on every card |
| Background | white cards, dark cover |

These keys are refused if they ever appear in a request: `brand_color`, `theme`,
`font`, `logo_override`, `template_css`, `master_id`. The fixture and live
clients both reject them as `GAMMA_TEMPLATE_LOCKED`.

The internal PptxGenJS renderer keeps its own copy of these values in
`apps/renderer/design_system/tokens/`. Two engines means two places to change a
colour; that duplication is known and tracked, not accidental.

## Cards and slots

One card per internal layout, so a Gamma deck and an internally rendered deck
carry the same story in the same order. Each slot draws from a subset of the
chapters the internal renderer already allows for that layout, which keeps the
two engines citing the same Framework evidence.

| Card | Layout | Slot | Framework chapters | Max chars |
| --- | --- | --- | --- | --- |
| 1 | `COVER_01` | `cover.title` | — (opportunity name) | 90 |
| 1 | `COVER_01` | `cover.client_name` | — (client name) | 80 |
| 1 | `COVER_01` | `cover.subtitle` | 1 Management summary | 160 |
| 2 | `EXECUTIVE_SUMMARY_01` | `executive_summary.body` | 1 Management summary | 2400 |
| 3 | `CONTEXT_01` | `context.summary` | 1, 2 Starting point | 2400 |
| 4 | `PROBLEM_SOLUTION_01` | `problem_solution.body` | 2, 4 The solution and to-be process | 2400 |
| 5 | `PROCESS_FLOW_01` | `process_flow.body` | 2, 4 | 2000 |
| 6 | `SCOPE_01` | `scope.in_scope` | 3 Aim & success measurement, 5 How it works in detail | 2000 |
| 7 | `REQUIREMENTS_MATRIX_01` | `requirements.body` | 5 | 2000 |
| 8 | `ARCHITECTURE_01` | `architecture.body` | 6 How it is built, 7 What we need from the client | 2000 |
| 9 | `COMPLIANCE_01` | `compliance.body` | 8 Security, data protection & human control | 2000 |
| 10 | `TIMELINE_01` | `timeline.body` | 10 Complexity, effort & timeline | 1600 |
| 11 | `MILESTONES_01` | `milestones.body` | 10 | 1600 |
| 12 | `TEAM_FTE_01` | `team.body` | 10 | 1600 |
| 13 | `SUCCESS_METRICS_01` | `success_metrics.body` | 3 | 1600 |
| 14 | `OPEN_QUESTIONS_01` | `open_questions.body` | 11 Trustworthiness - quality gates | 1600 |
| 15 | `NEXT_STEPS_01` | `next_steps.body` | 13 Next steps & glossary | 1600 |

Chapter 9 (Business case & ROI) feeds nothing. MS-14 forbids currency and ROI
pricing on `SUCCESS_METRICS_01`, and Gamma output never passes through the
SlideSpec validator that enforces it, so the chapter is excluded at the source
instead.

Chapters 0 (About this document) and 12 (Evolution stages) also feed nothing:
neither has a card in the internal deck.

## How a slot gets filled

`apps/api/services/gamma/slot_mapping.py` builds the slots:

1. Read the chapters the contract assigns to the slot, in order.
2. Flatten each chapter body — prose stays as-is, structured blocks are reduced
   to their text leaves — and join with a blank line.
3. Trim to `max_chars` at the nearest sentence or word boundary.
4. Drop the slot entirely if there is nothing grounded to say.

A thin Framework therefore yields a shorter deck rather than invented filler.
The two required slots, `cover.title` and `cover.client_name`, raise
`GAMMA_PAYLOAD_INVALID` if empty; the pipeline stops rather than shipping a
cover that says "Client".

## Data egress

Every chapter-fed slot is `client_confidential` in
[`config/data_egress_policy.yaml`](../../config/data_egress_policy.yaml) and is
individually allow-listed for the `gamma` provider. `cover.title` is `internal`
because it is the opportunity title we chose, not client text. Adding a slot to
the contract without adding it to the policy makes the live send fail closed
with `EGRESS_BLOCKED`; `tests/unit/gamma/test_jj26_template_contract.py` catches
that before it ships.
