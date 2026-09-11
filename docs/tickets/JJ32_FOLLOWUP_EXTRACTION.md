# JJ-32 — Follow-up extraction (transcript → JSON)

Phase 5. Owner: Jaya Joshi. Priority: P1. Kit:
[`FOLLOWUP_EMAIL_KIT.md`](FOLLOWUP_EMAIL_KIT.md).

Jaya owns everything that decides what the follow-up is allowed to claim.
Extraction is the content-grounding step: a raw, possibly noisy transcript
becomes a single JSON object, and nothing in that object may be inferred,
completed or embellished. MS-32 and BT-33 fill a template from this JSON; they
do not re-interpret the meeting.

This is the follow-up analogue of ES-40. Freeze the schema on day one so the
other two owners build against fixtures instead of waiting for a live extractor.

## What to deliver

A versioned system prompt plus a machine-readable schema. Input is the raw
transcript. Output is JSON only — no prose, no markdown fences.

Land and freeze:

[`packages/contracts/followup_extraction.schema.json`](../../packages/contracts/followup_extraction.schema.json)

with fixtures under `packages/contracts/fixtures/followup_extraction/`.

### Extraction rules

1. Use only what is stated in the transcript. If a field is not supported,
   return `null`.
2. `key_points`: the 3 most decision-relevant statements. Outcomes, not topics.
   "Interface will be REST, not SOAP" — not "we discussed the interface".
   Maximum 20 words each. Maximum 3 items; surplus is dropped, not summarised
   into a fourth bullet. The renderer then links to the protocol.
3. `action_items`: only commitments someone actually made. Verb-first.
   - `owner`: the name or organisation stated. If unclear, set `owner` to
     `null` and move the item to `open_questions` instead.
   - `due`: only if a date or deadline was explicitly named. Convert to
     `DD.MM.YYYY`. Relative dates ("next Friday") are resolved against
     `meeting_date`. If no date was named, use `"TBD"`. Never invent a date.
4. `decisions`: only statements framed as agreed, confirmed or decided.
5. `open_questions`: unresolved items, unanswered questions, missing input.
6. `confidence`: `"high"` if the transcript is clear on this field, `"low"` if
   you had to interpret. Any `"low"` field must also be listed in
   `review_flags`.
7. Language of the output content: English. Keep client-specific terminology,
   product names and system names verbatim as spoken.
8. Do not include small talk, scheduling chatter, or internal side remarks.
9. Maximum 5 `action_items`. If there are more, keep the five with named
   owners and nearest dues; list the overflow in `review_flags` as
   `action_overflow_see_protocol`.

### Output schema

```json
{
  "meeting_topic": "string",
  "meeting_date": "DD.MM.YYYY",
  "project_name": "string | null",
  "participants": [{ "name": "string", "organisation": "string | null" }],
  "key_points": ["string"],
  "decisions": ["string"],
  "action_items": [
    { "action": "string", "owner": "string", "due": "DD.MM.YYYY | TBD" }
  ],
  "open_questions": ["string"],
  "next_meeting": { "date": "DD.MM.YYYY", "time": "string" } | null,
  "confidence": {
    "key_points": "high | low",
    "action_items": "high | low"
  },
  "review_flags": ["string"]
}
```

`project_name` may be `null` in the extraction. MS-32 supplies it from project
statics; the model must not guess a project label. `meeting_date` comes from
the calendar when the pipeline has it, and from the transcript only when the
calendar value is absent.

Speaker labels may be wrong or missing. Do not invent speakers to create
owners.

## Done when

Given a fixture transcript, the extractor returns schema-valid JSON that
contains only stated facts. Unclear owners become `open_questions`, not
actions. Missing dates are `"TBD"`. Low-confidence fields appear in
`review_flags`. Surplus key points and actions are not smuggled into the JSON
as extra bullets.

## Proof

- Contract tests against `followup_extraction.schema.json`.
- Fixture: clear workshop transcript → 3 outcome-style key points, verb-first
  actions with owners, no small talk.
- Fixture: commitment with no owner → item in `open_questions`, not
  `action_items`.
- Fixture: "next Friday" with a known `meeting_date` → concrete `DD.MM.YYYY`.
- Fixture: no deadline named → `"TBD"`, never a guessed date.
- Fixture: noisy / missing speaker labels → `confidence.action_items` is
  `"low"` and `review_flags` is non-empty.
- Negative: invented decision, date or owner fails the fixture.
- Prompt version is persisted on the extraction call (same rule as ES-32).

## Depends on

Existing opportunity transcripts (already in the product). Calendar
`meeting_date` when BT-33 can pass it in; until then fixtures supply it.
MS-32 and BT-33 are consumers of the frozen schema, not blockers.
