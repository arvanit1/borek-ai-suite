# BT-33 — Follow-up pipeline (JSON → Outlook draft)

Phase 5. Owner: Blenard Tahiraj. Priority: P1. Kit:
[`FOLLOWUP_EMAIL_KIT.md`](FOLLOWUP_EMAIL_KIT.md).

Blenard owns the job stages and the only path that can create an email: JSON
in, Outlook draft out. Rendering is deterministic from the frozen template
and the frozen JSON. The pipeline never sends. The draft goes to the meeting
owner. MS-32's review is a required stage, not a courtesy screen.

Build the renderer against a JJ-32 fixture JSON and the MS-32 template string
on day one. Do not wait for a live extractor or the review UI.

## What to deliver

### 1. Rendering step (JSON → email)

Fill the MS-32 follow-up template with the JSON. Rules:

- Omit any block whose source array is empty. Do not leave placeholders,
  empty bullets or headings without content.
- Order action items by due date, ascending. `"TBD"` last.
- Render `"TBD"` as `date to be confirmed`.
- Do not add sentences that are not in the template.
- Total body length: maximum 150 words excluding greeting and signature.
- If `key_points` would exceed 3 or `action_items` would exceed 5, drop the
  extras and add the protocol link rather than lengthening the body.
- Output the finished email as plain text: subject line, then body.

### 2. Orchestration

```
Meeting recording
    ↓ transcription (Teams / Outlook recording — already in product)
Raw transcript
    ↓ FOLLOWUP_EXTRACTION (JJ-32)
Structured data
    ↓ FOLLOWUP_RENDERING (this ticket)
Draft email
    ↓ FOLLOWUP_DRAFT (Outlook draft, meeting owner)
    ↓ FOLLOWUP_REVIEW (MS-32, mandatory)
Sent  (human sends from Outlook; this pipeline does not)
```

- New job stages: `FOLLOWUP_EXTRACTION`, `FOLLOWUP_RENDERING`,
  `FOLLOWUP_DRAFT`. Show a step only when the backend reports it (BT-26 rule).
  Customer-facing names, no vendor names: "Extracting follow-up", "Preparing
  email", "Draft ready for review".
- The Outlook artefact is a **draft** in the meeting owner's mailbox. Calling
  send, or creating a draft addressed to the client before review, is a
  classified failure, not a retry.
- Failure stops at the stage that failed and preserves the JSON / draft
  already produced. Resume restarts from that stage.
- Duplicate clicks, refresh and reconnect must not create a second Outlook
  draft.

### 3. Draft / sent log

Persist every generated draft alongside the later sent version (subject,
body, timestamp, opportunity, meeting owner). Store the delta, not a second
copy of the transcript. That delta is the data set for improving JJ-32's
prompt. Sent bytes are captured when the meeting owner actually sends, or
explicitly marked `sent_unknown` if Outlook confirmation is unavailable —
never pretend a draft was sent.

### 4. Rollout gate

Start with two named projects, not all of them. Measure edit distance
(draft → sent) for four weeks before widening. The production profile
refuses follow-up generation for an unlisted project rather than half-writing
an email.

Client-confidential transcript and email bodies that leave Borek (LLM extract,
Outlook draft) need an O4 classification. Freeze the field list in this ticket
and classify it; do not wait on BT-32's Gamma allow-list.

## Done when

A fixture JSON produces a legal plain-text email: no leftover placeholders, no
empty headings, actions ordered with TBD last, body ≤ 150 words, TBD rendered
as "date to be confirmed". A live path produces an Outlook draft for the
meeting owner and never a sent client email. An unreviewed draft cannot be
addressed to the client. Draft and sent (or `sent_unknown`) are both logged.

## Proof

- Renderer unit tests: empty `open_questions` omits the block; empty
  `action_items` uses the no-actions fallback; `"TBD"` sorts last and renders
  as "date to be confirmed"; >3 key points do not appear as extra bullets.
- Negative: leftover `{{placeholder}}` fails the test.
- Negative: body over 150 words excluding greeting/signature fails.
- Negative: send API / client-addressed draft before review is refused.
- Job test: extraction failure stops at `FOLLOWUP_EXTRACTION`; a later resume
  does not re-create an Outlook draft that already exists.
- Audit: draft row and sent (or `sent_unknown`) row for the same
  opportunity, with no transcript body stored in the delta log.
- Rollout: unlisted project → classified refusal, no draft created.

## Depends on

JJ-32 for the frozen JSON schema and fixtures — not the live extractor.
MS-32 for the frozen template string, optional-block rules, and project
statics shape — not the review UI. Existing transcripts and opportunity jobs
(AT-56 / AT-57 resume). Outlook credentials from delivery; until they exist,
the renderer and job graph ship against a fixture mailbox client.
