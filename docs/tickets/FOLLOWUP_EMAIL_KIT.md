# Follow-up email kit

Added 11 September 2026. Split as **JJ-32**, **MS-32**, **BT-33**.

After the pitch deck, the next client artefact is the meeting follow-up email.
This kit is that artefact. It is not a second Framework and it is not a
transcript dump. The email stays short: a few sentences plus compact bullets.
Detail belongs in the attached protocol, not in the email body.

The kit contains three things, owned along the same verticals as the pitch
tickets rather than as layers of one feature:

| Piece | What it is | Ticket | Owner |
| --- | --- | --- | --- |
| Extraction prompt | Raw transcript → structured JSON | [JJ-32](JJ32_FOLLOWUP_EXTRACTION.md) | Jaya Joshi |
| Email template and review surface | What the client receives; what the meeting owner checks | [MS-32](MS32_FOLLOWUP_REVIEW.md) | Mayank Somwani |
| Rendering rules and pipeline | JSON → draft in Outlook; never auto-send | [BT-33](BT33_FOLLOWUP_PIPELINE.md) | Blenard Tahiraj |

The JSON layer is the freeze. Going transcript → email in one step looks
faster and removes the point where errors are catchable. Freeze
`packages/contracts/followup_extraction.schema.json` on day one; Mayank and
Blenard build against fixtures.

## Pipeline

```
Meeting recording
    ↓ transcription (Teams / Outlook recording)
Raw transcript
    ↓ JJ-32 extraction prompt → JSON
Structured data
    ↓ BT-33 rendering step → draft email
Draft in Outlook
    ↓ MS-32 human review (mandatory)
Sent
```

The human review step is not optional. The draft goes to the meeting owner,
never straight to the client.

## Hard rules (all three tickets)

- Maximum 3 key points and 5 next steps. If there are more, the email links to
  the protocol instead of listing them.
- Every action has an owner. No owner → it is not an action, it is an open
  question.
- Never invent a date. Unknown due date is `TBD`, not a guess.
- Nothing enters the email that was not said in the meeting.
- Formal clients (Sie-Kultur) replace the greeting with
  `Dear {{salutation}} {{last_name}},`.
- Total body length: maximum 150 words excluding greeting and signature.

## Rollout

- Store project-level static data (`project_name`, client salutation style,
  standard recipients, sender profile) once per project — the model must never
  guess it. That store is MS-32.
- Keep the JSON layer. JJ-32 owns the schema; the other two consume it.
- Log every generated draft alongside the sent version (BT-33). The delta is
  the data set for improving the prompt.
- Start with two projects, not all of them. Measure edit distance for four
  weeks before rolling out further.

## Review checklist (meeting owner)

- Every name and date correct
- Every action has a real owner
- No item in the email that was not said in the meeting
- `review_flags` empty, or each flag checked against the transcript
- Tone matches this client (Du/Sie, formal/informal)
- Attachment actually attached, if referenced
