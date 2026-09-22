# BT-34 Stage 1 intake API contract v1

Frozen for MS-33 on 2026-09-22. Backend scope only; BT-35 and BT-36 are not
implemented here. Requirements: supplied `Pitch_Factory_Feature_Redefinition_Mayank_Blenard_QA.pdf`
(21 September 2026) and the user's BT-34 implementation request. The referenced
sprint/ticket Markdown files were absent at the inspected HEAD.

## Existing opportunity resource

Use the existing authenticated endpoints, with the existing bearer token:

| Method | Path | Success |
| --- | --- | --- |
| POST | `/opportunities` | 201, full OpportunityResponse |
| PATCH | `/opportunities/{opportunity_id}` | 200, full OpportunityResponse |
| GET | `/opportunities/{opportunity_id}` | 200, full OpportunityResponse |
| GET | `/opportunities` | 200, owner's OpportunityResponse array |

The additive field is `stage1_intake: Stage1Intake | null`. Reuse top-level
`client_name`; do not put a second client name inside the intake object. Existing
`additional_client_information` and `followup_statics` remain independent.
The existing client pack contains generic notes and a multi-contact list but no
website, sales topic or distinct company description. Keeping the new singular
POC and Stage 1 fields in one nullable object avoids reinterpreting existing data.
FastAPI `/openapi.json` is the executable request/response definition. The model
is `apps/services/api/app/schemas/stage1.py`; opportunity models live in
`apps/services/api/app/schemas/opportunities.py`.

| Field within stage1_intake | Type | Validation |
| --- | --- | --- |
| `client_website` | string or null | Max 2,048 characters; absolute HTTP(S) URL, hostname, no embedded credentials or whitespace |
| `poc_name` | string or null | Max 200 characters |
| `poc_position` | string or null | Max 200 characters |
| `sales_topic_description` | string or null | Max 20,000 characters |
| `about_company` | string or null | Max 20,000 characters |

All five values and the whole object are optional for backward compatibility and
incremental intake saving. Empty/whitespace-only strings become null. Nonempty
text is preserved as supplied. Values must be strings, not numbers, objects or
booleans. NUL (`\u0000`) characters are rejected with 422 in every intake
string, keeping memory and PostgreSQL JSONB persistence compatible. Unknown nested keys are rejected. Voice/transcript text is **not** a
supported nested field. Client name, opportunity name and department retain
their existing required, nonempty-string create contract; language defaults to
`en` and PII redaction defaults to true.

Example create request (`Content-Type: application/json`):

```json
{
  "client_name": "Acme",
  "opportunity_name": "Invoice matching",
  "department": "Finance",
  "stage1_intake": {
    "client_website": "https://example.com",
    "poc_name": "Ada Lovelace",
    "poc_position": "Operations lead",
    "sales_topic_description": "Explore invoice matching automation",
    "about_company": "Sales reports that the company distributes equipment."
  }
}
```

The response is the existing full opportunity object (`id`, existing business
fields, `created_by`, `created_at`, `updated_at`, optional existing metadata), plus
`stage1_intake` containing the five fields above. Missing nested fields read as
null; old opportunities return `stage1_intake: null`.

PATCH behavior follows existing JSON-object fields: omission leaves intake
unchanged; an object replaces the entire saved intake object; `null` clears it.
Send all five current UI values when saving an edited form. For example:

```json
{"stage1_intake": {"sales_topic_description": "New sales topic"}}
```

This replaces the object and makes the other four fields null on reads. It does
not merge nested fields. Updating another opportunity field never clears intake.

Persistence uses the existing owner-scoped opportunity record, both memory and
Supabase adapters. The additive migration is
`apps/services/api/supabase/migrations/025_bt34_stage1_intake.sql`. It adds nullable
JSONB with an object/null constraint. Apply it before running the updated API
against Supabase. No production migration has been run in this task. Existing
RLS and create/update audit events apply.
The research and voice endpoints also audit the authenticated request intent
(`stage1_research.generate`, `stage1_voice.request`); these events do not imply
successful research or transcription.

## Research resource

`POST /opportunities/{opportunity_id}/stage1-research`, bearer auth, **no request
body**, returns 200 with JSON conforming to
`packages/contracts/stage1_research.schema.json` (version `1.0`). It reads the
saved intake, so save the opportunity first. This is on-demand generation; the
result is returned, not cached or persisted. Calling again uses current intake
and current evidence. It does not advance journey markers or generate a deck.

The output contains:

- `schema_version`, `opportunity_id`, `client_name`.
- `company_facts`: `description`, `headquarters`, `employee_headcount`,
  `decision_makers`, `revenue`. Each fact has `status`, `origin`, `value`,
  `source_refs`. Values are exact cited text (including units, ranges, names,
  positions, dates if present), not normalized numbers or inferred estimates.
- Verified fact: `status: "verified"`, `origin: "SOURCE_FACT"`, nonempty string
  `value` and nonempty source references (`source_id`, `locator`, `excerpt`).
- Unknown fact: `status: "unknown"`, `origin: "UNKNOWN"`, `value: null`,
  `source_refs: []`. Conflicting provider evidence stays unknown.
- `user_statements`: `origin: "USER_INPUT"`, `fields`: the provided intake values
  and reused client name. A sales claim is never relabeled verified. POC is not
  assumed to be a decision-maker.
- `borek_offering`: a cited service from existing AT-59 retrieval, or unknown.
  These are facts about Borek, never about the client.
- `hypothesis` and `product_relevance`: `origin: "AI_INFERENCE"`, `status` of
  `generated` or `unknown`, nullable `text`, and `basis` reference identifiers.
  Generated text is tentative, for review; it is never a verified company fact.
- `dependencies`: explicit unavailable-provider or unrun-generation markers.

No approved client web research adapter exists in this repository. Default
research therefore returns unknown client facts and
`COMPANY_RESEARCH_PROVIDER_UNAVAILABLE`. Website input is stored, never fetched.
There is no scraping or fallback to model memorization. A future approved adapter
implements `CompanyResearchProvider.research(client_name=..., client_website=...)`
and is wired by `app.services.stage1.get_company_research_provider`. It must bind
evidence to the exact client, enforce outbound-data rules, and supply cited
`CompanyEvidence` records in a list. Unknown evidence fields, malformed records,
missing citations and values absent from their cited excerpt fail with 502, even
when the malformed record conflicts with another source. Valid conflicting
values remain unknown. The API does not accept evidence from the caller.

In fixture mode no LLM call occurs: hypotheses are unknown and
`HYPOTHESIS_GENERATION_NOT_RUN` is returned. In existing live mode, a saved sales
topic and an unambiguous Borek service match allow the shared Claude client to
generate only the two hypothesis objects. With no match, return
`BOREK_OFFERING_UNAVAILABLE` and unknown hypotheses. The canonical schema validates
the assembled output. The LLM cannot populate the company fact fields.

The TypeScript type is generated by the existing generator into
`generated/typescript/contracts/stage1_research.ts`; JSON Schema remains the
runtime authority (including conditional provenance constraints).
The fixture `packages/contracts/fixtures/stage1_research.unknown.json` is ready
for MS-33 to render without a live research provider.

## Optional voice: explicit dependency boundary

`POST /opportunities/{opportunity_id}/stage1-voice`, bearer auth, optional
`multipart/form-data` field `file`:

- Missing file or zero bytes: 200 `{"status":"not_provided","transcript":null}`.
- Any nonempty file: 503 `STAGE1_VOICE_UNAVAILABLE`. No upload is accepted or
  persisted, no transcription is fabricated, and the saved topic is unchanged.

MS-33 can ship text intake and show the recording feature as unavailable. There
is no audio/transcription service to reuse, and no provider has been selected or
enabled by this change. **Voice transcription is not implemented/completed.**
An approved provider is needed first. Downstream consumption additionally needs
BT-36's summary contract. Do not route a recording through meeting transcript
upload, paste raw transcription into the sales topic automatically, or imply a
successful upload after receiving 503. No audio-format promise is frozen until
the provider contract exists.

## Errors and ownership

All routes retain the existing `{"error":{"code":"...","message":"...","detail":{}}}`
envelope (detail may contain existing validation details).

| Status | Meaning |
| --- | --- |
| 401 | Missing/invalid authentication |
| 404 | Opportunity not found or belongs to another user |
| 422 | Invalid request fields/UUID; intake mutation is not applied |
| 502 `STAGE1_RESEARCH_FAILED` | Provider failure, invalid evidence or invalid hypothesis/schema output; no source data in the error |
| 503 `STAGE1_VOICE_UNAVAILABLE` | Nonempty voice input cannot be accepted yet |

Existing storage failures retain the existing opportunity error codes.

## Prompt and downstream handoff

`services.framework.stage1_intake` builds one reusable `STAGE1_INTAKE_BEGIN` /
`STAGE1_INTAKE_END` block. It contains allowlisted single-line JSON marked
`USER_INPUT`, escapes injected delimiter strings, and applies the existing ES-4
redaction rules before live use. Raw voice/transcript keys are excluded.

The block is passed through existing Stage A orchestration to knowledge
extraction and framework synthesis, and used for Stage 1 research hypotheses.
No intake on a legacy opportunity means no new block. Downstream presentation
generation still consumes the existing framework. BT-35 can reuse the helper in
its document pipeline; BT-36 can reuse research output for its stage outputs.

Prompt-version, field-presence and SHA-256 metadata are logged, not customer
prompt bodies, consistent with AT-53/ES-32's prohibition on raw prompt logs.
Mocked tests capture actual prompt payloads to prove the block is present. Live
research calls reuse existing usage/latency logging and provider egress policy.
No new secrets or production policy entries are introduced.

The existing meeting transcript paths are unchanged. Their global conversion to
summary-only prompts is BT-36; this ticket does not claim that global rule is
already satisfied. First Contact document upload and transcript eligibility
changes are BT-35; MS-33 owns the form and hiding its transcript panel.

## Completion status

Text intake, prompt integration, research schema, evidence boundary and mocked
coverage are implemented locally. BT-34 is **not complete**: actual client
research and voice transcription providers, live migration verification, and
QA-01 acceptance remain outstanding. BT-35/BT-36 workflows and frontend UI are
outside this change.
