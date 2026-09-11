# MS-32 — Follow-up review surface and project statics

Phase 5. Owner: Mayank Somwani. Priority: P1. Kit:
[`FOLLOWUP_EMAIL_KIT.md`](FOLLOWUP_EMAIL_KIT.md).

Mayank owns every surface the meeting owner actually touches, plus the static
data the model must never guess. The client receives the email template. The
meeting owner receives a review screen and a checklist. Nothing is sent from
this ticket — sending is forbidden until BT-33 has an Outlook draft *and* this
review is confirmed.

Build the UI against a JJ-32 fixture JSON. Do not wait for a live extractor.

## What to deliver

### 1. Email template (what the client receives)

```
Subject: {{project_name}} — Follow-up {{meeting_topic}} ({{meeting_date}})

Hi {{recipient_first_name}},

thank you for your time {{time_reference}}. Below is a short summary of what
we agreed, so we all work from the same picture.

Key points
- {{key_point_1}}
- {{key_point_2}}
- {{key_point_3}}

Next steps
- {{action_1}} — {{owner_1}}, by {{due_1}}
- {{action_2}} — {{owner_2}}, by {{due_2}}
- {{action_3}} — {{owner_3}}, by {{due_3}}

{{open_question_block}}

If anything here does not match your understanding, just let me know and I
will correct it.

Best regards
{{sender_name}}
{{sender_role}} · BOREK
```

Formal clients (Sie-Kultur) replace the greeting with
`Dear {{salutation}} {{last_name}},`.

### 2. Optional blocks

Include only when the JSON actually supports them. Never leave a heading
without content, an empty bullet, or a leftover `{{placeholder}}`.

| Block | When to include | Text |
| --- | --- | --- |
| `{{open_question_block}}` | ≥1 unresolved question | Open from our side: - {{open_question_1}} - {{open_question_2}} |
| Decision block | Meeting produced a formal decision | Decisions - {{decision}} (agreed {{meeting_date}}) |
| Attachment line | A protocol/document is attached | Attached you will find {{attachment_name}} with the full detail. |
| Next meeting line | A follow-up date was named | Next session: {{next_meeting_date}}, {{next_meeting_time}}. |
| No-actions fallback | No action items were agreed | No action items from our side for now — we will come back to you once {{dependency}} is clarified. |

More than 3 key points or 5 next steps: do not list the extras. Link to the
protocol instead.

### 3. Placeholder sources

| Placeholder | Source | Format |
| --- | --- | --- |
| `{{recipient_first_name}}` | CRM / meeting invite | First name, or `{{salutation}} {{last_name}}` for formal clients |
| `{{project_name}}` | Project master data | Exact project label used with the client |
| `{{meeting_topic}}` | JJ-32 JSON | 2–4 words, e.g. Requirements Workshop |
| `{{meeting_date}}` | Calendar | `DD.MM.YYYY` |
| `{{time_reference}}` | Calendar | today / yesterday / on {{meeting_date}} |
| `{{key_point_x}}` | JJ-32 JSON | One line, ≤ 20 words, no filler |
| `{{action_x}}` | JJ-32 JSON | Verb-first, e.g. Deliver interface specification |
| `{{owner_x}}` | JJ-32 JSON | Named person or BOREK / `{{client_short}}` |
| `{{due_x}}` | JJ-32 JSON | `DD.MM.YYYY`, or TBD if no date was named |
| `{{sender_name}}`, `{{sender_role}}` | Sender profile | Static per team member |

Store project-level static data once per project: `project_name`,
`client_short`, salutation style (Du/Sie), standard recipients, sender
profile. The extractor must not invent these.

### 4. Review screen

On the opportunity, after a follow-up draft exists:

- Show subject + body as the meeting owner will send them.
- Show `review_flags` from the JSON. Each flag must be checked off against
  the transcript before confirm.
- Checklist (all required):
  - Every name and date correct
  - Every action has a real owner
  - No item in the email that was not said in the meeting
  - `review_flags` empty, or each flag checked
  - Tone matches this client (Du/Sie, formal/informal)
  - Attachment actually attached, if referenced
- Edits stay in the draft. Confirming review does not send. It marks the
  draft reviewed so BT-33 may leave it in the meeting owner's Outlook.
- The client is never a recipient of an unreviewed draft.

## Done when

A meeting owner opens a fixture draft, sees the short template (not a wall of
text), can edit, must complete the checklist, and cannot skip to send.
Formal-client statics produce `Dear {{salutation}} {{last_name}},`. Empty
`open_questions` / `decisions` / `next_meeting` omit those blocks rather than
rendering empty headings. Project statics round-trip on the opportunity and
are never asked of the model.

## Proof

- UI test: fixture JSON with 3 key points and 2 actions renders the template.
- UI test: empty `open_questions` omits the block; empty `action_items`
  shows the no-actions fallback.
- UI test: `salutation_style=formal` switches the greeting.
- UI test: confirm is disabled until every checklist item and every
  `review_flag` is acknowledged.
- UI test: confirm does not call a send API.
- Persistence: project statics survive reload; a second user cannot read the
  first user's sender profile (RLS).
- Fast-path screenshot: reviewed draft, checklist complete, Outlook still
  unsent (BT-33 holds send).

## Depends on

JJ-32 for the frozen JSON schema and fixtures — not for the live extractor.
BT-33 for the draft resource shape (`subject`, `body`, `review_flags`,
`attachment_name`, `status: draft|reviewed|sent`). Freeze that API on day
one; this ticket renders a fixture draft until the pipeline lands.
