# BT-34 to MS-33 handoff

2026-09-22. **READY: text-based Stage 1 intake and persistence. NOT READY: external company research and voice recording.** Backend contract is ready for Mayank's UI implementation; Supabase deployment still requires migration verification and application. BT-34 is not complete.

## Save and reopen the form

Use existing bearer authentication and opportunity endpoints. Create requires existing `client_name`, `opportunity_name`, and `department`; do not duplicate client name inside `stage1_intake`. No meeting transcript or recording is required.

`POST /opportunities` with `Content-Type: application/json`:

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

201 returns the full existing OpportunityResponse plus this intake object. `GET /opportunities/{id}` returns the persisted object; `GET /opportunities` returns the owner's opportunity array. Old records return `stage1_intake: null`. Missing nested fields read as null.

`PATCH /opportunities/{id}` returns 200 with the full opportunity:

| Request body | Saved result |
| --- | --- |
| `{"department":"Operations"}` | Existing intake preserved |
| `{"stage1_intake":{"about_company":"Updated"}}` | Entire intake replaced; other four fields read as null |
| `{"stage1_intake":null}` | Intake cleared to null |
| `{"stage1_intake":{}}` | Empty intake object; all five fields read as null |

For normal form editing, send **all five current values** in the replacement object. A single-field PATCH does not merge. Keep edits in the form if saving fails; hydrate from the successful response or GET after reopening.

All five fields are optional nullable strings. Website: max 2,048 characters and absolute HTTP(S), hostname, no credentials/whitespace/control characters. POC name and position: max 200 each. Topic and company text: max 20,000 each. Empty/whitespace-only strings normalize to null; nonempty text stays as supplied. Extra nested keys, non-string values and NUL characters fail validation. Display 422 errors without clearing saved intake. Retain existing 401 sign-in and 404 unavailable-opportunity behavior. Errors use `{"error":{"code":"...","message":"...","detail":{}}}`.

## Research UI: unavailable external capability

Do not label external research as completed or treat the website as fetched. The backend contract and unknown-data fixture are usable for UI development:

- `POST /opportunities/{id}/stage1-research`, bearer auth, no body; save intake first.
- 200 returns schema version `1.0` with `opportunity_id`, `client_name`, `company_facts`, `user_statements`, `borek_offering`, `hypothesis`, `product_relevance`, and `dependencies`.
- Each of the five client facts currently returns `{"status":"unknown","origin":"UNKNOWN","value":null,"source_refs":[]}` with `COMPANY_RESEARCH_PROVIDER_UNAVAILABLE`. Render **Unknown / research unavailable**, not zero, a successful research report, or sales claims as verified facts.
- User statements have `origin: USER_INPUT`; hypotheses have `origin: AI_INFERENCE`, status, nullable text and basis. Keep these visibly separate from cited SOURCE_FACT values. Borek offering evidence concerns Borek, not the client.
- Fixture mode returns unknown hypotheses and `HYPOTHESIS_GENERATION_NOT_RUN`. Existing live mode can invoke Claude for hypotheses when a saved topic matches an approved Borek service; that does **not** make external company research available. Avoid automatic calls on form load/save.
- Results are on demand, not persisted. The endpoint does not advance stages, create a job or produce a presentation. Invalid provider/model output returns 502 `STAGE1_RESEARCH_FAILED`.

Use [the canonical schema](../../packages/contracts/stage1_research.schema.json) and [unknown fixture](../../packages/contracts/fixtures/stage1_research.unknown.json). Generated TS type: `Stage1Research` in `generated/typescript/contracts/stage1_research.ts`, also exported by the contracts barrel.

## Recording UI: unavailable

Keep the optional recording control disabled with an unavailable explanation; text saving must work independently. `POST /opportunities/{id}/stage1-voice` takes optional multipart field `file`: missing/zero-byte input returns 200 `{"status":"not_provided","transcript":null}`; any nonempty input returns 503 `STAGE1_VOICE_UNAVAILABLE`. No recording is persisted or transcribed; the original topic is preserved. Never show success on 503, route this through meeting-transcript upload, or append raw transcription to the topic.

First Contact should hide the meeting-transcript panel. Document generation belongs to BT-35; voice-summary consumption and Stage 1/2 outputs belong to BT-36. Neither is delivered here.

Full details: [API contract](BT34_STAGE1_INTAKE_API.md). Release gates and dependencies: [stabilization report](BT34_STABILIZATION_REPORT.md).
