# New-direction tickets (JJ / MS / BT)

Proposed by `scripts/generate_team_plan_docx.py` (Consolidated Team Plan v1.0,
Head of AI direction 3 September 2026). Numbers above BT-27, JJ-25 and MS-26
were not in the original backlog.

## Six live tickets each, plus the follow-up email kit

JJ-26, JJ-27 and JJ-28 are landed, so they are owned but not workload. That
leaves eighteen live pitch items, split three ways along verticals rather than
layers — a layered split makes every feature cross all three owners.

On 11 September 2026 the follow-up email kit was added at the end of this
cut, one ticket each: JJ-32, MS-32, BT-33. Same verticals. Specs in this
folder; kit overview [`FOLLOWUP_EMAIL_KIT.md`](FOLLOWUP_EMAIL_KIT.md).

| Owner | Vertical | Live tickets | Specs |
| --- | --- | --- | --- |
| Jaya Joshi | Content grounding and deck fidelity | AT-59, ES-39, ES-40, JJ-29, JJ-30, JJ-31, **JJ-32** | [`docs/gamma/`](../gamma/), this folder |
| Mayank Somwani | User surface and filed history | AT-61, MS-27, MS-28, MS-29, **MS-31**, **MS-32** (MS-30 closed 11 Sep) | this folder |
| Blenard Tahiraj | Pipeline stages and release | AT-60, BT-28, BT-29, BT-30, BT-31, BT-32, **BT-33** | this folder |

Each owner holds exactly one earlier-range leftover, chosen so its only
consumers are that owner's own tickets:

- **AT-59** (live corpus and rate cards) → Jaya. ES-39 and ES-40 are the only
  things that read the corpus, and both are hers.
- **AT-61** (file into a real repository) → Mayank. MS-29 and MS-30 are the
  only consumers of filing metadata.
- **AT-60** (live credentials, real template id, error contract) → Blenard.
  BT-28 and BT-32 depend on it directly.

## Contracts to freeze before building

Cross-owner edges cannot be removed, only made non-blocking. Agree each shape
below first, then both sides build in parallel against a fixture.

| Handoff | Freeze this | So the consumer can |
| --- | --- | --- |
| ES-40 → BT-28 | [`gamma_payload.schema.json`](../packages/contracts/gamma_payload.schema.json) and fixtures in [`fixtures/gamma_payload/`](../packages/contracts/fixtures/gamma_payload/) | Build the stage against a fixture payload |
| JJ-31 → BT-31 | `stage_profiles` block and the stage enum | Enforce prerequisites against the enum |
| JJ-31 → BT-32 | Slot list per stage profile | Classify slots before they exist |
| AT-60 → JJ-29, MS-28 | Provider error contract and owned-host rule | Sign against a fixture host; map fixture errors |
| BT-28 → JJ-30 | Where the Gamma PDF lands on the version | Rasterise a fixture PDF |
| BT-31 → MS-31 | Eligibility response JSON | Render a fixture eligibility payload |
| AT-59 → BT-29 | Stage name `BOREK_RETRIEVAL` in [`knowledge_corpus.json`](../packages/contracts/knowledge_corpus.json) | Ship the label "Retrieving Borek information" behind "shown when reported" |
| ES-39 → MS-30 | Demo corpus id `borek-demo`, marker `demo` (live marker `es39`) | Seed against the marker |
| JJ-32 → MS-32, BT-33 | Follow-up JSON schema (landed by JJ-32 as `followup_extraction.schema.json`) and fixtures | Review UI and renderer build against a fixture JSON |
| MS-32 → BT-33 | Template string, optional-block rules, project-statics shape | Renderer fills a frozen template |
| BT-33 → MS-32 | Draft resource JSON (`subject`, `body`, `review_flags`, `status`) | Review screen renders a fixture draft |

BT-30 depends on everything by design — it is the acceptance gate and runs last.
That is not a dependency to engineer away. The follow-up kit is a later
vertical: it does not gate BT-30, and BT-30 does not gate it. Freeze the
three follow-up shapes above and JJ-32 / MS-32 / BT-33 start in parallel.

## Journey-stage work

The three cumulative outputs (First contact, Deepening, Concretisation) span
JJ-31 (stage profiles), BT-31 (prerequisites and prior-stage context) and MS-31
(selector UI), with MS-30 supplying the seed decks that make an unlocked state
demonstrable.

## Follow-up email kit

Added at the end of this cut, 11 September 2026. One ticket each, same
verticals. Does not gate BT-30.

- Kit: [`FOLLOWUP_EMAIL_KIT.md`](FOLLOWUP_EMAIL_KIT.md)
- Jaya — [`JJ32_FOLLOWUP_EXTRACTION.md`](JJ32_FOLLOWUP_EXTRACTION.md)
- Mayank — [`MS32_FOLLOWUP_REVIEW.md`](MS32_FOLLOWUP_REVIEW.md)
- Blenard — [`BT33_FOLLOWUP_PIPELINE.md`](BT33_FOLLOWUP_PIPELINE.md)

Assignment PDF: `Pitch_Factory_New_Tickets_Jaya_Mayank_Blenard.pdf`, generated
by `scripts/generate_jj_ms_bt_tickets_pdf.py`.

**Closure rule:** do not close until every Done when condition and required
proof is satisfied.
