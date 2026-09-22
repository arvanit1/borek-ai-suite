# BT-34 stabilization and verification

2026-09-22. **BT-34 remains incomplete. Text intake is ready for MS-33 implementation; external company research and voice recording are not ready. The complete validation gate is not green.** No BT-35/BT-36 implementation, commit, push, merge, PR, deployment or live database operation was performed.

This document records the completed stabilization pass before Git commit preparation.
The subsequent local foundation commit is described in the implementation report's
Git review preparation section; the historical HEAD and uncommitted-file counts below
are retained as verification evidence. No acceptance or validation status changed.

## A. Repository state (stabilization snapshot)

- Branch: `codex/bt34-stage1-intake`.
- HEAD: `9f5c669c6e03f1e83360f1bb55d37774b9036b47`.
- Local `origin/main` and remote main, checked with `git ls-remote`: `b1e63b5c169c641f79a96764ef0ae9d026d09b6a`. HEAD and origin/main have identical file trees.
- Starting work: 14 modified tracked files and 12 new files, all matching the previous implementation report. No unexpected changes. All were inspected; no reset, stash, discard, merge or replacement of existing work occurred.
- Stabilization changes four existing BT-34 files, updates two existing BT-34 documents, and adds this report and the MS-33 handoff. Final state: 14 modified tracked files and 14 new files. The original 14 tracked modifications remain intact; the other 20 initial files are byte-identical to the initial backup. All tested implementation files still match the validation snapshot. No dependency/package changes.
- A byte-for-byte backup of the initial uncommitted files is in `tmp/bt34-stabilization/initial-work.zip`. Tests ran against an isolated HEAD archive overlaid with current uncommitted files; hashes are in `tested-files.json`. Generated contract files were copied, and installed node_modules were reused through junctions. No `.env` was copied. Test-generated customer reports remain in the isolated copy, protecting existing workspace artifacts.

Sources: complete previous implementation report, API contract, actual code/tests/schema/fixture/migration and validation logs; supplied Feature Redefinition PDF (pages 2–5) and pasted user requirements. The PDF is requirements evidence, not authority to execute its suggested later-ticket work.

## B. Acceptance criteria

| Criterion | Verified state |
| --- | --- |
| A. Stage 1 intake persistence | PASS locally: five optional nullable fields; existing client name reused; create/get/list/update. Memory round-trip and mocked Supabase REST serialization/retrieval pass. Real Supabase persistence remains unverified. |
| B. Opportunity compatibility | PASS: legacy records/requests work, no required new fields, existing ownership and error conventions retained. |
| C. STAGE1_INTAKE prompts | PASS for existing orchestration/extraction/synthesis and research hypothesis paths. Structured USER_INPUT, delimiter escaping, ES-4 redaction and voice-key exclusion tested. Legacy opportunities add no block. Metadata/version/hash logs plus mocked actual-payload proof exist; raw prompt-body logging is prohibited by existing policy. Jaya must accept this proof for the PDF's “Prompts logged” criterion. |
| D. Company research schema | PASS: dedicated version 1.0 JSON Schema, canonical fixture, runtime validation and codegen registration. Actual research provider absent. |
| E. Provenance | PASS structurally: SOURCE_FACT + citations, USER_INPUT, AI_INFERENCE remain separate. POC is not promoted to decision-maker; Borek offering is not a client fact. |
| F. Unknown company facts | PASS for implemented boundary: missing/conflicting valid evidence stays unknown; model cannot populate client facts. Malformed evidence now fails before conflict resolution. An approved adapter must still prove company identity and factual adequacy; a substring citation check cannot independently establish truth. Hypotheses require review, not a claim of hallucination-proof generation. |
| G. Optional voice | PARTIAL: omission/empty file works; nonempty file returns explicit 503 without mutating topic. Recording/transcription and summarized downstream consumption are not implemented. |
| H. Framework/presentation compatibility | No new regression found in current verification. Existing no-intake behavior retained; full-pipeline fixture tests run separately. Twelve existing unit failures prevent claiming a fully passing compatibility gate. |
| I. MS-33 contract | READY for text UI: verified preserve/replace/clear semantics, validation, retrieval and unavailable states. Frontend form itself belongs to Mayank. |
| J. Migration | Static checks and adapter tests pass. Additive nullable JSONB; live/isolated SQL execution, RLS and deployed API round-trip proof outstanding. |

Existing meeting paths still use their prior transcript behavior. The sprint's global summary-only rule is **not** satisfied by BT-34; BT-36 owns it. First Contact document eligibility/output generation is not delivered here.

## C. Stabilization changes

1. `app/schemas/stage1.py`: reject NUL characters in every intake string with 422. Previously memory accepted input that PostgreSQL JSONB cannot store. Tests exercise POST/PATCH rejection for all five fields and ensure invalid PATCH preserves saved values.
2. `services/framework/stage1_research.py`: validate the complete provider evidence list, record types, known fields, nonempty citations and excerpt support before grouping conflicts. Previously malformed conflicting/unknown-field records could be silently ignored. Errors remain sanitized; valid conflicts still return unknown.
3. Use `provider is not None`, so a legitimate adapter with false boolean value is called rather than silently skipped without an unavailable marker.
4. Added malformed/falsey-provider regression coverage and explicit Supabase object replacement plus legacy missing-column normalization assertions. Updated the API validation contract and added [the MS-33 handoff](BT34_MS33_HANDOFF.md).

No provider was selected, activated or purchased. No unrelated failing test or implementation was changed.

## D. Validation

All Python verification used the existing `.venv` with external socket connections blocked by scratch `support/sitecustomize.py`; loopback remained available for local tests. `RUN_SUPABASE_INTEGRATION=0`. No paid provider calls or production database connections were executed. The known unmocked test was explicitly deselected, not retried with real credentials.

| Check | Result |
| --- | --- |
| BT-34 unit/integration + migration + audit tests | **56 passed**, including both previously addressed failures. `focused.log`. |
| `python scripts/validate_all.py` unit stage | **2,214 passed, 12 failed, 2 skipped, 1 deselected**. Stops at unit failures as designed. `validation.log`. |
| German review-summary test with only localization provider mocked; historical-job test isolated | **2 passed on current tree; 2 passed on original HEAD**. `current-mocked.log`, `baseline-mocked.log`. The mock verifies one real localization-path invocation; it does not certify live translation quality. |
| Formatting / syntax / whitespace | Black on all seven new Python files passes; all 20 modified/new Python files compile; `git diff --check` passes. |
| Generated research model | Generated Python `Stage1Research` imports and validates the canonical unknown fixture. JSON Schema remains the runtime provenance authority. |

All **71 remaining commands** from `validate_all.py` were executed in their original order with a diagnostic runner: **66 passed, 5 failed**. Full-pipeline integration: **17 passed**. Python and TypeScript generation, Python contract import checks, renderer/web typechecks, renderer server tests and all other frontend/renderer commands passed except the five listed below. Four failures duplicate unit-wrapper failures (`test:at15`, `test:at26`, `test:jj22`, `test:jj23`); the additional web `test:bt27` failure was also reproduced on original HEAD. There is no claim of a green full gate.

Logs are under `tmp/bt34-stabilization/`; `remaining-results.json` records each exact command and exit code. The diagnostic runner continues after failures solely to expose results; it does not turn a failed gate into success.

Reproduce focused coverage:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/api/test_bt34_stage1_intake.py tests/unit/framework/test_bt34_stage1_research.py tests/integration/full_pipeline/test_bt34_intake_research.py tests/unit/api/test_at37_migration_verification.py tests/unit/api/test_at52_audit_log.py -q
```

For broad unit reproduction, retain the external-network guard and add:
`PYTEST_ADDOPTS=--deselect=tests/unit/framework/test_review_insights.py::test_es36_review_summary_respects_framework_language`.
The repository also excludes `live_claude` tests through its existing pytest configuration. Do not remove those safeguards to obtain a green gate.

## E. All 16 previously reported failures

Test IDs below are repository-relative. “No BT-34 blocker” means not attributable to this text-intake change; **every remaining required-gate failure still prevents a green overall release gate** and needs independent resolution or an explicit project disposition. Historical baseline evidence is `tmp/bt34_baseline_failures.log` (12 failed, historical-job test passed); its snapshot is original HEAD. Newly inspected renderer details are in `baseline-at15.log` and `baseline-at26.log`.

| Test | Exact failure / current result | Original HEAD? / BT-34 path impact | Blocks BT-34? / next action |
| --- | --- | --- | --- |
| `tests/unit/api/test_at37_migration_verification.py::test_apply_migrations_script_covers_001_through_024` (now `_025`) | Old expected migration numbering omitted existing duplicate 024 and new 025. Current corrected test passes. | Old assertion also mismatched existing duplicate 024; BT-34 adds 025. | Addressed; retain both existing 024 files and verify execution on disposable DB. |
| `tests/unit/api/test_at52_audit_log.py::test_state_changing_routers_import_and_call_record_audit_event` | Previous audit-call count 17 was below 18 mutation handlers. Current test passes with new route audit events. | BT-34 added handlers; original unrelated baseline not required to establish this mismatch. | Addressed; audits denote request intent, not successful unavailable capabilities. |
| `tests/unit/api/test_bt_live_slide_generation.py::test_llm_client_passes_structured_request_to_executor` | External payload blocked: unclassified `/renderLanguage`. | Reproduced on HEAD; egress/client code unchanged. | No text-intake blocker; provider/egress owner must reconcile field classification. |
| `tests/unit/api/test_bt_live_slide_generation.py::test_group_a_cover_makes_one_openai_call_and_validates` | Structured generation fails before mocked executor: blocked `/renderLanguage`. | Reproduced on HEAD; slide/egress path unchanged. | Same independent egress fix. |
| `tests/unit/api/test_bt_live_slide_generation.py::test_openai_slide_error_has_no_fixture_fallback` | Expected regex `transport unavailable`; actual `Structured generation failed for COVER_01: External payload contains blocked or unclassified fields: /renderLanguage`. | Reproduced on HEAD; unchanged. | Same independent egress fix, then retest transport assertion. |
| `tests/unit/eval/test_es33_fixtures.py::test_es33_expected_matches_deterministic_pipeline[invoice_3way_match]` | `assert actual == expected` fails: framework chapters/review/attention content differs from expected fixture. | Reproduced on HEAD. BT-34 touches pipeline signature/optional live synthesis forwarding, but this deterministic `use_llm=False`, no-intake case does not execute that addition. | No BT-34 regression; framework owner must review semantic differences before updating fixtures. |
| `tests/unit/eval/test_es33_fixtures.py::test_es33_expected_matches_deterministic_pipeline[minimal_invoice_match]` | Same framework equality assertion; chapters/review/attention differences. | Reproduced on HEAD; same nonexecuted BT-34 path. | Same independent fixture/behavior review. |
| `tests/unit/eval/test_es33_fixtures.py::test_es33_expected_matches_deterministic_pipeline[warehouse_delivery_match]` | Same equality assertion; review_summary / attention_signals / attention differ. | Reproduced on HEAD; same nonexecuted BT-34 path. | Same independent fixture/behavior review. |
| `tests/unit/gamma/test_gamma_spike.py::test_fixture_client_satisfies_provider_contract` | `client_logo_applied` is False, expected True. | Reproduced on HEAD; Gamma/logo code unchanged. | No text-intake blocker; Gamma owner reconcile fixture logo contract. |
| `tests/unit/gamma/test_gamma_spike.py::test_client_logo_reference_is_optional` | With-logo result False, expected True. | Reproduced on HEAD; unchanged. | Same independent logo investigation. |
| `tests/unit/renderer/test_add_data_table.py::test_at26_renderer_unit_checks` | npm assertion at `addDataTable.test.ts:171`: BT-24 slide 5 width `'5.625' !== '5.854'`. | Reproduced on HEAD, including fresh direct npm rerun; renderer unchanged. | No text-intake blocker; renderer owner confirm intended table width. |
| `tests/unit/renderer/test_jj22_golden_deck.py::test_jj22_group_b_golden_deck_regression` | `process_flow_01.png`: 8,344 pixels differ; centroid shift 0.2903px horizontal / 4.8047px vertical; spacing profile 31px, content band 20px. | Reproduced on HEAD; renderer/golden fixtures unchanged. | No text-intake blocker; compare intended layout and approved golden. |
| `tests/unit/renderer/test_jj23_golden_deck.py::test_jj23_executive_summary_golden_deck_regression` | `executive_summary_01.png`: 15,361 pixels differ; centroid shift 0.1120px / 16.6997px; spacing 31px, content band 32px. | Reproduced on HEAD; unchanged. | Same independent visual baseline review. |
| `tests/unit/renderer/test_master_cover.py::test_at15_renderer_unit_checks` | `MASTER_COVER.test.ts:66`: strict numeric equality `4.861000000000001 !== 4.861`. | Reproduced on HEAD, including fresh direct npm rerun; unchanged. | No text-intake blocker; renderer owner review numeric tolerance. |
| `tests/unit/api/test_at56_job_reconnection.py::test_multiple_historical_jobs_resolve_to_latest` | Prior run returned older job UUID after both completed. Now passes broad current run and isolated HEAD/current runs. | Did not reproduce on original HEAD in historical/fresh isolation. BT-34 touches only opportunity data in memory store, not timestamps or job selection. Selector uses UUID lexical order when completion timestamps tie: a plausible pre-existing timing cause, not proven from unavailable prior timestamps. | Not a demonstrated BT-34 regression; job owner add deterministic clock/tie-case investigation separately. |
| `tests/unit/framework/test_review_insights.py::test_es36_review_summary_respects_framework_language` | Prior Anthropic authentication failure from empty German customer-view chapters causing fallback localization. Excluded from broad run; passes with provider mock. | Authentication failure deliberately not re-executed on HEAD. Same test, review/customer-view/localization code on both trees; mocked behavior passes both. | No BT-34 regression established; test owner should isolate localization transport in a separate test-maintenance change. |

Additional failure exposed after the unit gate (not counted among the original 16):

| Test/command | Exact failure | Original HEAD / BT-34 impact | Blocking / next action |
| --- | --- | --- | --- |
| `npm run test:bt27 --workspace borek-web` / `apps/web/src/lib/jobStageContract.test.ts:123` | `backend JobStage.FOLLOWUP_EXTRACTION has no customer-facing label in jobProgress.ts` | Fresh reproduction on original HEAD in `baseline-bt27.log`; job enum and frontend label paths unchanged by BT-34. | No text-intake regression; still blocks the overall gate. Frontend/job-contract owner must reconcile labels in a separate change. |

Confirmed current BT-34 defects were the NUL persistence gap and provider-evidence handling described in C; both now have passing regression coverage. No newly failing legacy path was found. The two originally addressed tests pass on the current implementation.

## F. Database migration readiness

`025_bt34_stage1_intake.sql` adds nullable JSONB with an object-or-SQL-NULL constraint, no default/backfill and no destructive data change. Existing rows receive null; existing opportunity columns/RLS remain untouched. Reapplication preserves valid intake objects. It follows existing ADD IF NOT EXISTS / DROP CONSTRAINT IF EXISTS conventions. The repository migration runner sorts complete filenames, so both existing 024 migrations run before 025. Do not rename previously applied 024 files. A deployment tool that keys solely on numeric versions must reconcile that existing collision before rollout.

Memory and Supabase stores both preserve omitted intake, replace provided objects, and accept explicit null; adapter tests verify this without a database. `scripts/verify_db.py` includes the new column in EXPECTED_COLUMNS, but that presence check does not prove its type/nullability, data preservation or RLS behavior.

Docker is installed but its Linux engine is unavailable; `psql`, `postgres` and `initdb` were not found. **No isolated SQL test or live migration was run.** Do not deploy the updated Supabase API before migration 025 is verified and applied through the approved deployment process.

Required pre-deployment procedure, on a disposable local Supabase/PostgreSQL environment only:

1. Start a dedicated disposable local Supabase stack (auth schema/roles are needed for the full chain), with no production secrets or mounted production data. Explicitly validate connection host is loopback, port belongs to that instance, and database name/server identity match the disposable target. Use an isolated repo copy without `.env`.
2. Execute `scripts.apply_migrations.migration_files()` in its returned filename order through both 024 files. Seed synthetic owner-A/owner-B opportunities using existing required fields and record full row snapshots/counts.
3. Execute the exact 025 SQL. Assert legacy rows equal their prior snapshots after removing the new field; every new value is SQL NULL. Inspect `information_schema.columns`: `data_type=jsonb`, `is_nullable=YES`, no default. Check `pg_get_constraintdef` for object/null enforcement.
4. Write `{}` and a complete valid intake object to synthetic records; snapshot them. Execute 025 again. Assert object values and all pre-existing fields/counts remain identical. In rolled-back savepoints, assert arrays, strings, numbers and JSON literal null violate the constraint; SQL NULL must succeed.
5. Run `scripts.verify_db.verify_via_postgres(explicit_local_url)` directly and require `(0, True)`. **Do not use the current verifier CLI for this local test:** it intentionally bypasses loopback PostgreSQL and can fall back to REST. Direct invocation avoids loading `.env` or selecting an external fallback. Its smoke insert/delete must remain confined to the disposable database.
6. Against that local stack, exercise authenticated API POST/GET/list and all three PATCH semantics using the real Supabase adapter. Restart the API and verify retrieval. Assert owner B cannot read, update, research or upload voice against owner A's opportunity. Run `tests/integration/api/test_rls_negative.py -m integration` with only explicit disposable local settings and `RUN_SUPABASE_INTEGRATION=1`.
7. Save schema, preservation, reapply, RLS and API logs for Blenard/Jaya review. Only then schedule a separately approved non-production deployment verification; production remains outside this task.

## G. MS-33 handoff readiness

[BT34_MS33_HANDOFF.md](BT34_MS33_HANDOFF.md) supplies exact requests, response expectations, field limits, errors and UI behavior. [API contract v1](BT34_STAGE1_INTAKE_API.md) matches implementation. The canonical research schema and fixture remain unchanged.

**READY:** text create/edit/save/reload with no transcript or recording prerequisite. Omitted intake preserves; an object replaces; null clears, confirmed by tests for both storage implementations (Supabase transport mocked).

**NOT READY:** external client research and recording/transcription. Keep unavailable UI states explicit. Research 200 with unknown facts is not successful external research. Live hypothesis generation can still use existing Claude; avoid automatic requests on load/save. Research is not persisted. Nonempty voice always returns 503.

## H. Dependencies and decision owners

| Dependency | Implemented / missing | Blocks text intake? | Blocks full BT-34? | Next owner and information needed |
| --- | --- | --- | --- | --- |
| Approved company research provider | Interface, schema, citations, unknown/failure handling and mock proof / approved adapter and real-source validation absent | No | Yes | Project's authorized provider approver (not identified), then Blenard: approved vendor/source scope, company identity rules, data-egress permission, credentials, budget, rate limits, evidence/freshness and failure policy. |
| Approved voice transcription provider | Optional empty/unavailable endpoint preserves topic / actual recording acceptance, transcription, retention/error contract absent | No | Yes | Authorized provider approver, Blenard and Mayank: vendor, supported formats/duration/size/languages, consent/retention rules, credentials/cost limits and UI error contract. Do not promise formats before approval. |
| BT-36 summary integration | Raw voice excluded from new prompts / structured summary contract and pipeline absent | No | Yes for safe downstream voice consumption | Blenard as BT-36 owner, coordinated with Mayank: frozen summary schema, job/error states, mapping of summary to supplemental intake without replacing original topic. Global pipeline remains separate work. |
| Database execution verification | Nullable migration, static checks, adapter mocks / disposable SQL, reapply, RLS and deployed round-trip proof absent | No for local development; yes for Supabase rollout | Yes | Blenard/deployment owner: disposable local infrastructure first, approved non-production target later, migration ledger including duplicate 024 handling and evidence logs. |
| QA-01 | Automated backend proof and MS-33 handoff / five signed-off scenarios and end-to-end UI/provider proof absent | No for backend/UI development; required for accepted delivery | Yes | Jaya Joshi, with Mayank and Blenard: deployed MS-33/BT-34/BT-35 prerequisites, complete five-scenario definitions, voice/research evidence and accepted prompt-log proof. PDF names five scenarios but does not detail them; do not invent sign-off criteria. |

## I. Exact conditions to close BT-34

Close only after approved research/transcription integrations satisfy their contracts; correct-company sourced facts and unknown/conflict cases are demonstrated; optional voice works while preserving the original topic and obeying the BT-36 summary boundary; disposable/non-production migration and persistent owner-scoped API proof pass; MS-33 integration and QA-01's five scenarios receive Jaya's sign-off; prompt proof is accepted under existing logging restrictions; and required validation failures receive resolution or an explicit authorized disposition. Provider interfaces, schemas and mocks alone do not fulfill those conditions. QA-03 remains the later sprint release gate.

## J. Recommended next development action

Give Mayank the text-intake handoff now and obtain project-owner decisions on the two providers. In parallel with that project coordination, arrange disposable migration verification and assign the existing gate failures to their owning workstreams. Do not start BT-35/BT-36 implementation under this stabilization task. Keep BT-34 open until the conditions above are met.
