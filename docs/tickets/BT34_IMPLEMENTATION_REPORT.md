# BT-34 local implementation report

2026-09-22. **BT-34 is not complete.** Text intake, prompt integration, research
contract and provider boundaries are implemented locally. Actual external client
research and voice transcription remain unavailable. No BT-35 or BT-36 workflow
was implemented.

## Git review preparation - 2026-09-22

This report is included in the single local review commit titled
`BT-34: implement Stage 1 intake and research foundation` on
`codex/bt34-stage1-intake`. Sections A and H record the historical implementation
state before that commit; the stabilization addendum records the later test results.
The manifest below covers all 28 intended implementation/stabilization files.
No unrelated changes or secret candidates were found. Temporary logs, backups,
validation snapshots and generated model/type artifacts remain ignored and excluded.
Implementation files match the tested stabilization snapshot, so no provider calls
or test reruns were needed for commit preparation. Only documentation was clarified.
The branch is ready for code review of the backend foundation, not ticket closure
or deployment. No push, PR, merge or production operation is part of this delivery.
**BT-34 remains incomplete; all documented blockers and failed gates still apply.**

## A. Repository state (implementation snapshot)

| Item | Before | After |
| --- | --- | --- |
| Branch | `blenard` | `codex/bt34-stage1-intake` |
| Local HEAD | `9f5c669c6e03f1e83360f1bb55d37774b9036b47` | unchanged |
| Local origin/main ref | `3c32317b6dd86c93a645df4cfbd0296ca0de2e63` | `b1e63b5c169c641f79a96764ef0ae9d026d09b6a` after fetch |
| Remote main | Verified with `git ls-remote` as `b1e63b5c169c641f79a96764ef0ae9d026d09b6a` | unchanged by this task |
| Working tree | Clean; no pre-existing uncommitted work | Uncommitted BT-34 changes listed below |

Remote main is the merge of the inspected blenard HEAD. Their Git tree hashes
are identical (`52cca43ec41567e52eb44690034a5bf31a889023`); no code divergence
required resolution. A local branch was created without merge/rebase/reset.

The four requested sprint/ticket documents were missing, and no newer BT-34/35/36
implementation specs were found. Requirements came from the supplied PDF and
pasted user request. No parent or repository AGENTS.md was found.

## B. Existing functionality and reuse

- FastAPI opportunity POST/PATCH/GET/list APIs, bearer authentication and ownership checks.
- Pydantic request/response models, memory and Supabase REST stores, nullable JSONB migration conventions.
- Existing client-pack fields remain unchanged. New Stage 1 fields are distinct because
  that pack has generic notes/multiple contacts but no website or sales topic.
- Existing Stage A orchestration, knowledge extraction and framework synthesis prompt builders.
- ES-4 redaction, shared Claude structured output, provider egress checks, AT-53/ES-32
  usage logging and AT-52 audit events.
- AT-59 approved Borek service retrieval, used only for Borek product relevance.
  It is not a client-company research provider.
- Existing JSON Schema, Python/TypeScript generators, pytest and validation infrastructure.

No audio transcription service or approved client-company research provider was found.

## C. BT-34 implementation

1. Additive nullable `stage1_intake`, persisted and retrieved through the existing
   opportunity APIs. Reuses `client_name`; supports website, POC name/position,
   original sales topic and company free text. Unknown fields and invalid values
   are rejected; null/empty values and old opportunities remain supported.
2. One reusable `STAGE1_INTAKE` builder, passed through the existing orchestration
   into extraction/synthesis and research hypotheses. Values are source-only JSON,
   tagged USER_INPUT; delimiter strings are escaped. Voice keys are excluded.
   Redaction applies before provider use. Existing opportunities without intake
   get no new block.
3. On-demand research endpoint with validated dedicated JSON. Facts come only
   from cited provider evidence; unsupported/conflicting facts remain unknown.
   Sales statements, verified facts and AI hypotheses are separate. The LLM can
   write only hypotheses/product relevance; it cannot populate fact fields.
   Unsupported numeric claims in hypotheses and invalid source references are rejected.
4. Explicit research-provider interface with no scraping/fabricated fallback.
   Reuses approved Borek service retrieval for relevance.
5. Voice dependency boundary: missing/empty input is optional; nonempty input
   returns 503 rather than pretending transcription succeeded. No audio is stored,
   no topic is overwritten and no raw voice is injected into generation prompts.
6. Request audit events, metadata-only prompt logging, nullable migration, generated
   contract types, frontend fixture and focused tests. Database verification now
   expects the new column. Migration-chain validation preserves both existing 024 files.

File manifest is at the end of this report. Generated model/type outputs remain
Git-ignored according to existing repository policy.

## D. Frozen contracts / MS-33 interface

- API contract: `docs/tickets/BT34_STAGE1_INTAKE_API.md`.
- Research schema: `packages/contracts/stage1_research.schema.json`.
- Example response: `packages/contracts/fixtures/stage1_research.unknown.json`.
- Generated TypeScript: `generated/typescript/contracts/stage1_research.ts`,
  with `Stage1Research` exported from the generated barrel.
- Generated Python: `generated/python/contracts/stage1_research.py`.

Mayank should save `stage1_intake` on the existing opportunity resource and read
it back there. PATCH replaces the nested object; omit it to preserve it, or send
null to clear it. Call `POST /opportunities/{id}/stage1-research` without a body
after saving. Render unknown facts and dependency markers explicitly. The voice
control must remain unavailable until the provider is implemented.

## E. Tests and validation

Commands ran from the repository root using `.venv\Scripts\python.exe`. No live
database/migration was run. BT-34 provider tests use mocks. Counts below describe
individual runs and overlap; they must not be added as unique coverage totals.

| Command / check | Result |
| --- | --- |
| `python -m pytest tests/unit/api/test_at58_client_information_logo.py tests/unit/api/test_es38_stage_a_client_pack.py tests/unit/framework/test_synthesis.py tests/unit/framework/test_es38_client_pack.py -q` | 27 passed |
| `python -m pytest tests/unit/api/test_bt34_stage1_intake.py tests/unit/framework/test_bt34_stage1_research.py tests/integration/full_pipeline/test_bt34_intake_research.py -q` | Final focused run: 31 passed |
| Same focused paths plus `tests/unit/api/test_at37_migration_verification.py` and `tests/unit/api/test_at52_audit_log.py` | Final run after audit/migration fixes: 44 passed |
| `python scripts/validate_all.py` | Failed at unit stage: 2,199 passed, 16 failed, 2 skipped; later gate stages did not execute |
| `python -m pytest tests/integration/full_pipeline -q` with `RUN_SUPABASE_INTEGRATION=0` | 17 passed |
| Original-HEAD isolated snapshot: `python -m pytest <13 failed test IDs> -q` | 12 failed, 1 passed; IDs in `tmp/bt34_baseline_test_ids.json` |
| `python -m pytest tests/unit/api/test_at56_job_reconnection.py::test_multiple_historical_jobs_resolve_to_latest -q` on final working tree | 1 passed |
| Python generator tests within the broad unit run | Passed, generated new Python model |
| `node scripts/generate_typescript.js` after final generator edit | Passed; 19 modules generated |
| Generated `Stage1Research.model_validate()` on the frozen fixture | Passed |
| `npm run typecheck --workspace borek-web` | Passed |
| `npm run typecheck --workspace borek-renderer` | Passed |
| `black --check --target-version py312` on the seven new Python files | Passed |
| `py_compile.compile(..., doraise=True)` on all 20 changed Python files | Passed |
| `git diff --check` | Passed |

No standalone repository Python lint/type-check command is configured in
pyproject.toml. Black was applied only to new Python files to avoid unrelated
formatting changes. Existing files were reviewed and whitespace/compilation checked.

The broad gate's 16 failures break down as follows:

- **2 addressed:** the migration chain assertion (including its existing duplicate
  024 numbering) and new POST-handler auditing. Final 44-test rerun passes these.
- **12 reproduced at original HEAD:** three live-slide tests blocked by the existing
  `/renderLanguage` egress classification; three ES-33 expected-framework fixture
  comparisons; two Gamma fixture/logo assertions; renderer data-table and cover
  assertions; Group B and executive-summary golden image differences.
- **1 intermittent:** historical-job selection failed in the broad run but passed
  in both original-HEAD and final-tree isolation. Not claimed fixed.
- **1 not rerun:** `test_es36_review_summary_respects_framework_language` made an
  unmocked Anthropic request with the test API key and failed authentication. No
  successful paid generation was observed. That network request was not repeated;
  no baseline-pass claim is made for this test.

The entire gate is therefore **not green**, and it was not rerun wholesale after
the targeted fixes. Logs: `tmp/bt34_validation.log`, `tmp/bt34_integration.log`,
`tmp/bt34_baseline_failures.log`, `tmp/bt34_typescript_codegen.log`. The baseline
snapshot is an ignored `git archive HEAD` extraction, not a branch switch/reset.
One tracked customer-report cache file rewritten by tests was restored byte-for-byte
to its inspected starting content; no pre-existing user changes were present.

## F. Dependencies / blockers

1. Approved company research provider absent. The default response explicitly
   returns unknown client facts and `COMPANY_RESEARCH_PROVIDER_UNAVAILABLE`.
2. Audio/transcription provider absent. Nonempty voice input returns
   `STAGE1_VOICE_UNAVAILABLE`; actual recording transcription is unimplemented.
3. BT-36 summary contract required before downstream voice text can be consumed.
   Existing global transcript paths have not been migrated to summary-only input.
4. Migration 025 is written, not applied or verified against live Supabase. Storage
   tests use memory and mocked production REST adapter transport.
5. QA-01 sign-off and integrated MS-33 UI validation remain outstanding. The broad
   suite failures above also prevent a clean release-gate claim.

## G. Handoff

Ready for Mayank: stable text intake persistence, read/update semantics, research
response schema/types/fixture and explicit unavailable-feature responses. The
frontend can implement and test MS-33 without pretending unavailable research or
recording functionality is ready.

BT-35 still owns client-document upload/processing, document-driven First Contact
generation and transcript-stage eligibility. BT-36 still owns summary-only
transcript use, Stage 1/2 output sets, agenda/decks/email and journey completion
markers. These workflows, pricing and existing presentation rendering were not changed.

## H. Git and delivery (implementation snapshot)

All implementation is local and uncommitted on `codex/bt34-stage1-intake`.
No commit, push, merge, rebase, PR, deployment, secrets change, production
configuration change or external production mutation was performed. Fetch only
refreshed the local remote-tracking ref. **Do not close BT-34 on this evidence.**

## File manifest

Modified (14):

- `apps/api/services/framework/pipeline.py`
- `apps/api/services/framework/synthesis.py`
- `apps/api/services/knowledge_model/extraction.py`
- `apps/services/api/app/routers/opportunities.py`
- `apps/services/api/app/schemas/opportunities.py`
- `apps/services/api/app/services/audit/audit_log.py`
- `apps/services/api/app/services/data/memory_store.py`
- `apps/services/api/app/services/data/supabase_store.py`
- `apps/services/api/app/services/stage_a_orchestration.py`
- `scripts/generate_pydantic.py`
- `scripts/generate_typescript.js`
- `scripts/verify_db.py`
- `tests/unit/api/test_at37_migration_verification.py`
- `tests/unit/api/test_at52_audit_log.py`

Created (14, including stabilization documentation):

- `apps/api/services/framework/stage1_intake.py`
- `apps/api/services/framework/stage1_research.py`
- `apps/services/api/app/schemas/stage1.py`
- `apps/services/api/app/services/stage1.py`
- `apps/services/api/supabase/migrations/025_bt34_stage1_intake.sql`
- `docs/tickets/BT34_IMPLEMENTATION_REPORT.md`
- `docs/tickets/BT34_STABILIZATION_REPORT.md`
- `docs/tickets/BT34_MS33_HANDOFF.md`
- `docs/tickets/BT34_STAGE1_INTAKE_API.md`
- `packages/contracts/fixtures/stage1_research.unknown.json`
- `packages/contracts/stage1_research.schema.json`
- `tests/integration/full_pipeline/test_bt34_intake_research.py`
- `tests/unit/api/test_bt34_stage1_intake.py`
- `tests/unit/framework/test_bt34_stage1_research.py`



## Stabilization addendum - 2026-09-22

The follow-up stabilization pass is documented in [BT34_STABILIZATION_REPORT.md](BT34_STABILIZATION_REPORT.md); [BT34_MS33_HANDOFF.md](BT34_MS33_HANDOFF.md) is the concise frontend handoff. Historical results above are preserved, but the following are the latest conclusions:

- Starting branch/HEAD/main and all 26 uncommitted files matched this report; existing work was preserved. No commit, push, merge, PR or live database operation.
- Fixed NUL input acceptance (memory/PostgreSQL JSONB mismatch), malformed provider evidence bypassing validation during conflict/unknown-field handling, and falsey provider selection. Added regression coverage plus explicit Supabase replacement/legacy-row checks. Updated the API contract's validation details; field names and research schema v1 remain unchanged.
- Focused BT-34 + migration/audit validation: **56 passed**. Both previously addressed failures pass.
- Broad unit validation: **2,214 passed, 12 failed, 2 skipped, 1 deselected**. All 12 failures match the original-HEAD baseline. The intermittent historical-job test passes now; unchanged timestamp/UUID selection remains a plausible cause. The unmocked Anthropic test was excluded and verified with only its provider mocked on both original HEAD and current work; no paid calls/authentication retry.
- All 71 remaining validation-script commands were run separately: **66 passed, 5 failed**. Full-pipeline integration **17 passed**; codegen and both typechecks pass. Four failures repeat existing renderer failures; web `test:bt27` additionally fails because FOLLOWUP_EXTRACTION lacks a UI label, also reproduced on original HEAD. The complete gate is **not green**.
- No local migration execution was possible: Docker engine unavailable and PostgreSQL tools absent. The stabilization report contains the exact disposable verification procedure, including the verifier CLI's localhost/REST fallback limitation.
- **READY: text intake and persistence contract for MS-33. NOT READY: external company research and voice recording. BT-34 remains open** pending provider decisions/integrations, BT-36 summary consumption, migration proof, required gate disposition and Jaya's QA-01 sign-off. Global summary-only transcript behavior remains unimplemented, as previously stated.
