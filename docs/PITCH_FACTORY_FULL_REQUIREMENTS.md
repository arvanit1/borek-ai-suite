# Pitch Factory — Complete Requirements Reference

**Purpose:** Single handoff document for full project context (aligned with `main` + Continuation Development Backlog v1.0, 1 September 2026).  
**Sources:** `BOREK_Pitch_Factory_Continuation_Development_Backlog.pdf`, `Development_Task_Backlog_Detailed.pdf`, `Framework_and_Presentation_Pipeline_Full_Technical_Plan_v2.pdf`.  
**Last updated:** 2026-09-01 (session snapshot on branch `arvanit`, main at `7101fd7`).

---

## Table of contents

1. [Product outcome & scope decisions](#1-product-outcome--scope-decisions)
2. [Final acceptance journey](#2-final-acceptance-journey)
3. [Release gates (definition of done)](#3-release-gates-definition-of-done)
4. [Continuation backlog — 24 tracked tickets (full specs)](#4-continuation-backlog--24-tracked-tickets-full-specs)
5. [Original development backlog — all numbered tickets](#5-original-development-backlog--all-numbered-tickets)
6. [API contract (technical plan §22)](#6-api-contract-technical-plan-22)
7. [Database (technical plan §23)](#7-database-technical-plan-23)
8. [Execution waves & dependency chains](#8-execution-waves--dependency-chains)
9. [Current implementation status snapshot](#9-current-implementation-status-snapshot)
10. [Arvanit (AT) — are we done?](#10-arvanit-at--are-we-done)
11. [Verification commands](#11-verification-commands)
12. [Known live blockers (not AT)](#12-known-live-blockers-not-at)

---

## 1. Product outcome & scope decisions

### Primary product outcome

Upload transcripts → AI Framework → **human approval** → **automatic** planning → **automatic** slide generation → validation → PPTX/PDF rendering → preview → download.

### Key scope decisions (continuation backlog)

- Keep **explicit human Framework approval** as the default governance checkpoint.
- After approval: Plan → Slides → Validation → Rendering → Preview continue **automatically** (no manual Plan/Deck steps in default mode).
- Framework must export to **PDF, HTML, and real Word DOCX** (full Framework information; not HTML renamed as `.docx`).
- **EXECUTIVE_SUMMARY_01** must become a real generated and rendered layout, not a stub.
- Jobs must survive long generation times, refreshes, and reconnects **without false failure states**.
- Normal users see **customer-facing concepts**, not internal layout IDs, UUIDs, schemas, or rendering internals.

### Team (continuation focus)

| Developer | Code | Primary continuation focus |
|-----------|------|----------------------------|
| Blenard Tahiraj | BT | Automation, orchestration, final integration (BT-25–27) |
| Arvanit Telaku | AT | Platform, APIs, jobs, security, observability (AT-56–57 + original closure) |
| Endrit Shemsedini | ES | Framework intelligence, privacy, review signals (ES-36–37 + ES-4, ES-32) |
| Jaya Joshi | JJ | Provenance, Framework UX, result UX (JJ-23–25 + JJ-9, JJ-22) |
| Mayank Somwani | MS | Recent work, recovery UX, responsive polish (MS-24–26) |

---

## 2. Final acceptance journey

```
Login
  → Create presentation
  → Upload transcript(s)
  → Generate
  → AI builds Framework
  → Review customer story
  → Download Framework Word/PDF if desired
  → Approve & build presentation
  → Automatic planning
  → Automatic slide generation and validation
  → Automatic PPTX/PDF rendering
  → Live progress
  → Presentation ready
  → Preview
  → Download PowerPoint / PDF
```

**Release ownership:** BT-27 integrates all work and owns end-to-end release acceptance.

---

## 3. Release gates (definition of done)

### Gate A — Original acceptance closure

- ES-4 and ES-32 closed.
- AT-8, AT-40, AT-41, AT-47, AT-53 closed.
- AT-37 and AT-38 verified with **live proof**.
- JJ-9 and JJ-22 closed.
- EXECUTIVE_SUMMARY_01 fully supported via JJ-23.

### Gate B — Framework completeness

- PII policy works per opportunity.
- Per-fact evidence is trustworthy.
- Human review remains explicit.
- Framework PDF, HTML, and Word DOCX export all work.
- DOCX contains all 14 chapters and complete meaningful Framework information.
- Prompt/model activity is durably auditable.

### Gate C — Automated presentation flow

- User clicks **Approve & build presentation** once.
- Plan, SlideSpecs, validation/compression, PPTX/PDF render, preview — all automatic.

### Gate D — Reliability and security

- No false four-minute timeout.
- Refresh/reconnect preserves active jobs.
- Duplicate jobs are not accidentally created.
- Failed stages can be retried/resumed sensibly.
- RLS tenant isolation is proven.

### Gate E — Product UX

- Users do not need SlideSpec, schemas, Celery, layout IDs, compression internals, UUIDs, or renderer internals.
- Framework review is **summary-first** with detail on demand.
- Presentation completion emphasizes preview and **Download PowerPoint**.
- Recent work and recovery states are understandable.

---

## 4. Continuation backlog — 24 tracked tickets (full specs)

**Closure rule (every ticket):** Do not close until every **Done when** condition and required proof is satisfied.

### ES-4 — Per-opportunity PII redaction (P0, ES, original)

**Goal:** Redaction policy configurable per opportunity, not hardcoded globally.

**Implementation:**
- Persisted opportunity-level PII-redaction configuration.
- Default safest approved behavior.
- Stage A reads opportunity setting; apply before every transcript-to-LLM operation.
- One opportunity’s policy must not affect another.
- Reuse existing redaction implementation.

**Done when:** A and B can have different settings; LLM input follows each; tests enabled/disabled; no transcript extraction regression.

**Proof:** Unit enabled/disabled, persistence, Stage A E2E two opportunities, names/emails/phones regression.

---

### ES-32 — Persist prompt versions with production jobs (P0, ES, original)

**Goal:** Prompt-version auditable on real extraction/Framework jobs.

**Implementation:** Every relevant ES LLM call identifies actual prompt version; persist with AT-53 `llm_calls`; link job/stage/opportunity; config-accurate version; survives restart.

**Done when:** Completed production job shows prompt version for every relevant ES LLM call.

**Proof:** Prompt-version persistence, multiple versions, worker restart, job association. **Depends on AT-53.**

---

### ES-36 — Framework Review Summary Model (P0, ES, continuation)

**Goal:** Concise structured review layer over 14 chapters (UI must not invent business logic).

**Implementation:** Provide executive_summary, key_pain_points, key_requirements, target_outcomes, assumptions, open_questions, contradictions, evidence_warnings, readiness, blocking_items — derived only from Framework/Knowledge Model; no unsupported claims; traceable; EN/DE.

**Done when:** Default Framework review UI can render meaningful concise summary without reconstructing logic from arbitrary chapter fields.

**Proof:** Strong opportunity, missing info, contradiction, weak evidence, German, provenance.

---

### ES-37 — Framework Review Attention Signals (P0, ES, continuation)

**Goal:** Deterministic signals for what requires human attention before approval.

**Implementation:** At minimum: READY_TO_APPROVE, REVIEW_RECOMMENDED, BLOCKING_CONTRADICTION, MISSING_REQUIRED_INFORMATION, WEAK_EVIDENCE; human-readable reasons; affected fields/chapters; no auto-confirm.

**Done when:** JJ-24 can distinguish safe review, optional review, mandatory intervention.

**Proof:** Fixture per state, blocking precedence, reason text, affected-field mapping. **Depends on ES-36.**

---

### AT-8 — Remove silent clipping from compression/retry (P0, AT, original)

**Goal:** Fail-closed compression; no deterministic clipping on live path.

**Implementation:** Remove silent text clipping; over-limit → semantic compression/retry; revalidate; preserve retry budget; explicit fail when exhausted; no sentence cut for max-length only.

**Done when:** Oversized SlideSpecs become valid via semantic compression OR fail explicitly; no hidden truncation accepts invalid output.

**Proof:** Oversized string, oversized arrays, compression success, exhaustion, assertion proving no clipping.

---

### AT-37 — Prove Supabase migrations from clean database (P0, AT, original)

**Goal:** Repeatable proof migration chain builds DB from zero.

**Implementation:** Clean Supabase/Postgres; apply full sequence; verify tables/indexes/relationships/policies; safe reapply; no manual production state; document procedure (`docs/database_migration_verification.md`).

**Done when:** Clean database entirely from repo migrations.

**Proof:** Clean apply, idempotent reapply, schema assertions.

---

### AT-38 — Prove RLS tenant isolation (P0, AT, original)

**Goal:** Two real authenticated users; User B cannot access User A data.

**Implementation:** Cross-user API and direct Supabase where applicable; opportunity, transcript, Framework, presentation; repeatable automated tests.

**Done when:** User B cannot read/manipulate User A protected data.

**Proof:** Cross-user GET, transcript/framework/presentation isolation, direct DB rejection. **Depends on AT-37.**

---

### AT-40 — Complete opportunity/transcript API contract (P1, AT, original)

**Goal:** Close §22.1 gap — transcript DELETE with ownership/persistence.

**Implementation:** `DELETE /opportunities/{id}/transcripts/{transcriptId}`; ownership + transcript belongs to opportunity; storage cleanup; structured errors; audit event.

**Done when:** All documented opportunity/transcript endpoints implemented with expected shapes.

**Proof:** Success delete, not found, wrong opportunity, unauthorized, storage behavior.

---

### AT-41 — Complete Framework API + PDF/HTML/DOCX rendering (P0, AT, original)

**Goal:** Professional Word report of complete Framework version.

**Implementation:**
- Complete generate, get, patch, regenerate chapter, confirm, render endpoints.
- `GET …/render?format=pdf|docx|html`.
- Real DOCX (`python-docx`), not HTML renamed.
- Metadata (Borek/client/opportunity), version, status, dates, executive overview, quality/readiness, open items.
- All 14 chapters canonical order; tables, lists, assumptions, warnings, evidence refs.
- Professional headings, page breaks; EN/DE; export without mutating stored object; draft labeled draft.

**Done when:** PDF/HTML/DOCX work; DOCX opens in Word with complete info; 14 chapters; correct version/status.

**Proof:** PDF, HTML, DOCX validity, chapters, version, EN/DE, tables/lists, evidence, draft vs confirmed.

---

### AT-47 — True per-fact Framework evidence + robust editing (P0, AT, original)

**Goal:** Trustworthy human review with per-fact evidence.

**Implementation:** No chapter-level refs shown as supporting every fact; each fact shows own evidence; nested editable; schema-valid persist; no silent provenance loss; confirmed immutable; provenance kinds differentiated; conversation IDs in expandable details.

**Done when:** Reviewer identifies source per fact, edits, saves, reloads with same values and evidence.

**Proof:** Fact-specific refs, different refs per fact, nested edit persistence, confirmed immutability, evidence after edit.

---

### AT-53 — Durable AI observability (P0, AT, original)

**Goal:** Production LLM records linked to jobs; survive restarts.

**Implementation:** Persist request_id, job_id, opportunity_id, stage, provider, model, prompt_version, token counts, latency, retry, timestamp, status/error, estimated cost; API+worker same store; no full confidential prompt bodies; aggregate into job metrics.

**Done when:** Real Framework/deck job has durable non-zero AI metrics matching actual calls.

**Proof:** Framework/planner/slide/compression calls, restart, retry, aggregated cost, privacy.

---

### AT-56 — Durable active-job reconnection (P0, AT, continuation)

**Goal:** Recover correct active job after refresh/navigation.

**Implementation:** Deterministic latest/current job per opportunity/stage; resume monitoring; no duplicate enqueue on refresh; completed/failed states correct; multiple jobs deterministic; RLS protected.

**Done when:** Refresh/reopen in-progress opportunity resumes original job monitoring.

**Proof:** Refresh during framework/slides, after completion, wrong user, multiple historical jobs.

---

### AT-57 — Failed-stage retry/resume infrastructure (P1, AT, continuation)

**Goal:** Resume from checkpoint; don’t redo successful earlier stages.

**Implementation:** Restart points for planning, slides, validation, rendering, preview; preserve Framework/Plan/SlideSpecs/artifacts; transient auto-retry within budget; retryability in job state; **non-retryable validation requires user review**; auditable retry; no silent overwrite of approved versions.

**Done when:** Late-stage failure resumes from appropriate checkpoint without repeating successful work.

**Proof:** Retryable provider failure, non-retryable validation, rendering failure, resume from plan, audit history.

---

### BT-25 — Automated Presentation Pipeline Orchestration (P0, BT, continuation)

**Goal:** After Framework approval, auto-run to completion.

**Implementation:** Primary **Approve & build presentation**; auto enqueue planning → observe → auto presentation generation → slides → validation → render → previews; Plan Preview optional; duplicate-click/refresh protection; confirmed-Framework gate; fail at correct stage preserving prior work.

**Done when:** No user action between Approve and “Your presentation is ready” on success path.

**Proof:** Successful chain, planning/deck failure, duplicate-click, refresh/reconnect, unconfirmed rejection.

---

### BT-26 — Live Generation Progress Experience (P0, BT, continuation)

**Goal:** Customer-facing progress for multi-minute jobs.

**Implementation:** Map job stages to labels (Preparing, Reading transcripts, … Building PowerPoint, Preparing preview); completed/current/upcoming + elapsed; no fake percentages; no false 4-minute timeout; never running+timeout together; connection loss ≠ job failed; auto transition to completed view.

**Done when:** 5–8 minute job visibly progresses; never falsely failed because browser stopped polling.

**Proof:** Stage mapping, long job, failed/completed, reconnect, conflicting-banner prevention.

---

### BT-27 — Final Automated E2E Integration Gate (P0, BT, continuation)

**Goal:** Release acceptance of full automated journey.

**Implementation:** Integrate AT/ES/JJ/MS continuation; no manual Plan/Deck in default; no dead ends; reload/reconnect; actionable errors; correct version links; EN E2E pass; DE smoke; security/provenance intact.

**Done when:** Clean user: sign in → upload → framework → review/export → approve → auto deck → preview → download PPTX/PDF without developer intervention.

**Depends on:** BT-25, BT-26, AT-41, AT-56, JJ-24, JJ-25, MS-24/25.

---

### JJ-9 — Group B field-level provenance (P0, JJ, original)

**Goal:** Group B same field-level provenance standard as rest of pipeline.

**Implementation:** fieldProvenance on all Group B layouts; every scalar leaf has valid chapter provenance; missing/unknown paths/chapters fail; root sourceChapterIds = union of field IDs.

**Done when:** Every Group B field traceable; invalid provenance rejected.

---

### JJ-22 — Resolve Group B golden regression (P1, JJ, original)

**Goal:** Fix TIMELINE_01 visual mismatch without blind golden update.

**Implementation:** Inspect actual vs approved; fix renderer OR approved reference update; full Group B golden suite passes.

**Done when:** All Group B golden regressions pass.

**Current blocker:** `timeline_01.png` — 1344px color mismatch (fails `validate_all.py`).

---

### JJ-23 — EXECUTIVE_SUMMARY_01 end-to-end (P0, JJ, continuation)

**Goal:** Stub → full supported layout.

**Implementation:** Dedicated SlideSpec schema; chapter sources; grounded content; field provenance; limits; AT-8 compression; real renderer; register gen+dispatch; remove Stage B skip; full test suite.

**Done when:** Planner selects layout; valid SlideSpec; renderer works; golden passes.

**Current:** Still stub in dispatcher; stripped from persisted plans.

---

### JJ-24 — Summary-first Framework Review UI (P0, JJ, continuation)

**Goal:** Concise decision UX; detail on demand.

**Implementation:** Summary first (ES-36/37); blocking prevents bad approve; 14 chapters accessible; customer wording; primary **Approve & build presentation**.

**Done when:** First-time user can decide without reading all 14 chapters first.

**Depends on:** ES-36, ES-37, AT-47.

---

### JJ-25 — Presentation Ready Experience (P1, JJ, continuation)

**Goal:** Strong completion screen.

**Implementation:** “Your presentation is ready”; PPTX primary, PDF secondary; auto-preview; metadata; hide layout IDs; Details for diagnostics.

**Done when:** Success path clear preview/download without internal terminology.

---

### MS-24 — Recent Presentations (P1, MS, continuation)

**Goal:** Persistent home/resume without UUID/history.

**Implementation:** List recent work with customer statuses (Draft, Analyzing, Needs review, Building, Ready, Needs attention); Open/Resume/Download; user isolation; empty state.

**Done when:** Returning user finds work without opportunity UUID.

---

### MS-25 — User-friendly failure and recovery (P1, MS, continuation)

**Goal:** Understandable failure states, not raw API errors.

**Implementation:** Categories: CONNECTION_LOST, STILL_RUNNING, RETRYING, INPUT_REQUIRED, VALIDATION_NEEDS_REVIEW, TERMINAL_FAILURE; hide stack traces; AT-56/57 integration; single dominant banner.

**Done when:** Common failures actionable for customers.

---

### MS-26 — Responsive and visual cleanup (P1, MS, continuation)

**Goal:** Cross-screen polish after structural UX lands.

**Implementation:** Responsive sidebars; one primary action; fewer nested borders; hide UUIDs/layout IDs; spacing; breakpoints tested.

**Done when:** Coherent at desktop/tablet/mobile; no horizontal overflow.

---

## 5. Original development backlog — all numbered tickets

**148 original tickets substantially complete per continuation plan; 11 still open (listed in continuation register).** Below: every numbered ticket from the detailed development backlog for cross-reference.

### Endrit (ES-1 – ES-35)

| Ticket | Done when (summary) |
|--------|---------------------|
| ES-1 | Accept .txt/.vtt/.srt/.docx; reject others clearly |
| ES-2 | Speaker turns for all four formats |
| ES-3 | Stable conversation_id on transcript + opportunity |
| ES-4 | PII redaction toggle per opportunity before LLM |
| ES-5 | Claude extraction → KnowledgeModel |
| ES-6 | source_refs on every fact |
| ES-7 | origin classification + confidence |
| ES-8 | Contradiction detection → conflict objects |
| ES-9 | Claude synthesis → 14-chapter FrameworkObject |
| ES-10 | Conflict resolution in synthesis |
| ES-11 | Quality scores 0–100 + rationale |
| ES-12 | regenerate_chapter updates one chapter only |
| ES-13 | Pre-confirm consistency (ch.6 AI used/not used) |
| ES-14–ES-27 | Per-chapter content requirements (§8 technical plan) |
| ES-28 | No invented facts without source_refs |
| ES-29 | One opportunity per object |
| ES-30 | Layered system prompt |
| ES-31 | Schema validation + retry |
| ES-32 | Version prompt templates with job log |
| ES-33 | Fixture transcript set |
| ES-34 | Unit tests extraction/synthesis |
| ES-35 | AI eval dataset contribution |

### Arvanit (AT-1 – AT-57)

| Ticket | Done when (summary) |
|--------|---------------------|
| AT-1 | FrameworkObject JSON Schema in packages/contracts |
| AT-2 | PresentationPlan schema |
| AT-3 | Base SlideSpec schema |
| AT-4 | Pydantic codegen |
| AT-5 | TypeScript codegen |
| AT-6 | schema_version + additive fields |
| AT-7 | Generic constraint validator |
| AT-8 | Compression/retry (no silent clip) |
| AT-9 | LibreOffice render-validation pipeline |
| AT-10 | Render checks (slide count, blank slides) |
| AT-11–AT-13 | Color, typography, spacing tokens |
| AT-14–AT-18 | Slide masters (DEFAULT, COVER, SECTION, CONTENT, CLOSING) |
| AT-19–AT-32 | Shared renderer components |
| AT-33 | Renderer dispatcher skeleton |
| AT-34 | FastAPI scaffolding |
| AT-35 | Celery + Redis |
| AT-36 | Job stage state machine |
| AT-37 | Supabase migrations |
| AT-38 | RLS policies |
| AT-39 | Supabase Auth |
| AT-40 | Opportunity + transcript endpoints §22.1 |
| AT-41 | Framework endpoints + render PDF/HTML/DOCX |
| AT-42 | Presentation plan generate |
| AT-43 | Presentation generate (confirmed gate) |
| AT-44 | Slide regenerate / change-layout |
| AT-45 | Job status endpoint |
| AT-46 | Upload UI |
| AT-47 | Framework review/edit UI per-fact evidence |
| AT-48 | Plan preview UI |
| AT-49 | Deck preview/download center |
| AT-50 | Docker Compose full stack |
| AT-51 | .env.example complete |
| AT-52 | Audit log infra |
| AT-53 | AI observability logging |
| AT-54 | Full pipeline integration test harness |
| AT-55 | Golden-deck test runner |
| AT-56 | Active-job reconnection (continuation) |
| AT-57 | Failed-stage retry/resume (continuation) |

### Blenard (BT-1 – BT-24 + BT-25–27 continuation)

| Ticket | Done when (summary) |
|--------|---------------------|
| BT-1 | OpenAI planner → PresentationPlan |
| BT-2 | Registry-only layoutId validation |
| BT-3 | Chapter-to-layout mapping table |
| BT-4–BT-8 | Group A SlideSpec schemas |
| BT-9–BT-13 | Group A content generation calls |
| BT-14 | sourceChapterIds enforcement Group A |
| BT-15 | Content limits Group A (e.g. COVER_01 statBadges max 3) |
| BT-16 | Group A compression/retry integration |
| BT-17–BT-21 | Group A renderers |
| BT-22 | Group A dispatcher registration |
| BT-23–BT-24 | Group A tests + golden fixtures |
| BT-25–BT-27 | Automation, progress UX, E2E gate (continuation) |

### Jaya (JJ-1 – JJ-25)

| Ticket | Done when (summary) |
|--------|---------------------|
| JJ-1–JJ-4 | Group B SlideSpec schemas |
| JJ-5–JJ-8 | Group B content generation |
| JJ-9 | Group B sourceChapterIds / field provenance |
| JJ-10–JJ-14 | Limits, business rules, compression |
| JJ-15–JJ-19 | Group B renderers + dispatcher |
| JJ-20–JJ-22 | Group B tests + golden (JJ-22 **failing**) |
| JJ-23–JJ-25 | EXECUTIVE_SUMMARY_01, summary UI, ready UX (continuation) |

### Mayank (MS-1 – MS-26)

| Ticket | Done when (summary) |
|--------|---------------------|
| MS-1–MS-5 | Group C SlideSpec schemas |
| MS-6–MS-10 | Group C content generation |
| MS-11–MS-15 | Provenance, limits, business rules, compression |
| MS-16–MS-21 | Group C renderers + dispatcher |
| MS-22–MS-23 | Group C tests + golden |
| MS-24–MS-26 | Recent presentations, failure UX, responsive (continuation) |

---

## 6. API contract (technical plan §22)

All `:generate` / `:regenerate` endpoints are **async** (return `job_id`; poll `GET /jobs/{jobId}`).

### §22.1 Opportunities & transcripts

- `POST /opportunities`
- `GET /opportunities/{id}`
- `POST /opportunities/{id}/transcripts`
- `GET /opportunities/{id}/transcripts`
- `DELETE /opportunities/{id}/transcripts/{transcriptId}`

### §22.2 Framework

- `POST /opportunities/{id}/framework:generate`
- `GET /frameworks/{id}`
- `PATCH /frameworks/{id}`
- `POST /frameworks/{id}/chapters/{chapterId}:regenerate`
- `POST /frameworks/{id}:confirm`
- `GET /frameworks/{id}/render?format=pdf|docx|html`

### §22.3 Presentation

- `POST /frameworks/{id}/presentation-plan:generate`
- `GET /presentation-plans/{id}`
- `POST /presentation-plans/{id}/presentation:generate`
- `GET /presentations/{id}`
- `GET /presentations/{id}/preview`
- `GET /presentations/{id}/download`

### §22.4 Slides

- `PATCH /presentations/{id}/slides/{slideId}`
- `POST /presentations/{id}/slides/{slideId}/regenerate`
- `POST /presentations/{id}/slides/{slideId}/change-layout`

### §22.5 Jobs

- `GET /jobs/{jobId}`

---

## 7. Database (technical plan §23)

**Ten core tables:** opportunities, transcripts, transcript_sections, framework_versions, presentation_plans, presentations, presentation_versions, slides, generation_jobs, audit_log.

**Follow-on migrations (001–015):** llm_calls, job runtime fields, PII flag on opportunities, etc.

**RLS:** enabled on all user data tables; policies per owner (`users_own_*`).

---

## 8. Execution waves & dependency chains

### Wave 1 — Start immediately

- AT: AT-8, AT-37, AT-40, AT-53
- ES: ES-4, ES-36
- JJ: JJ-9, JJ-22, JJ-23
- BT: Begin BT-25
- MS: MS-24

### Wave 2 — Dependency unlocks

- AT-37 → AT-38; AT-40 → AT-41 → AT-47; AT-53 → ES-32
- ES-36 → ES-37 → JJ-24
- AT-56 → BT-26

### Wave 3 — Product automation

- BT-25 → BT-26; JJ-24 → JJ-25; MS-25 → MS-26; AT-57 when reconnect stable

### Final gate

- **BT-27** after BT-25 + BT-26 + JJ-24 + JJ-25 + AT-41 + AT-56

### Critical chains

```
AT-37 → AT-38
AT-53 → ES-32
AT-40 → AT-41 → AT-47
ES-36 → ES-37 → JJ-24
AT-56 → BT-26
BT-25 + BT-26 + JJ-24 + JJ-25 + AT-41 + AT-56 → BT-27
```

---

## 9. Current implementation status snapshot

*(Updated 2026-09-03 from `main` at `90871f0` plus live Supabase proof)*

| Area | Status |
|------|--------|
| Framework generation (live) | Working (~6 min) |
| Framework Word/PDF download UI | Working (Framework review → Export panel) |
| Presentation planning (live) | Working |
| Deck generation live blocker | COVER_01 badge overflow fix merged in PR #65 |
| AT unit/integration proofs | Confirmed AT suites pass; see `docs/ARVANIT_DELIVERY_CHECKLIST.md` |
| Live DB verify (AT-37) | Full 16-migration reapply and schema verification pass |
| Live RLS (AT-38) | Direct negative test 1/1 and authenticated HTTP suite 7/7 pass |
| Live LLM persist (AT-53) | Hosted persistence test 1/1 pass |
| Full `validate_all.py` | Previous JJ-22 and COVER_01 blockers are merged; deterministic fixture gate is isolated from live Supabase configuration |
| EXECUTIVE_SUMMARY_01 | JJ-23 merged in PR #61 |
| Auto pipeline after approve | BT-25/26/27 merged in PRs #59/#60/#64 |
| Summary-first Framework UI | JJ-24/25 merged before PR #61 |
| Branch state | `main` equals `origin/main` at `90871f0`; AT work through PR #63 is merged |

---

## 10. Arvanit (AT) — are we done?

### Continuation + original AT tickets — implementation status

| Ticket | Implementation | Automated proof | Manual / merge |
|--------|----------------|-----------------|----------------|
| AT-8 | Done (fail-closed; no array clip) | `test_compression_retry.py` pass | — |
| AT-37 | Done | `verify_db.py`, `test_at37_*` pass | Live proof documented |
| AT-38 | Done | Live 7/7 with integration flag | — |
| AT-40 | Done | `test_transcripts.py` pass | — |
| AT-41 | Done (API + DOCX + download UI) | `test_at41_*` 12/12 pass | Word download verified in UI |
| AT-47 | Done (API + UI per block source_refs) | API + `test:at47` pass | — |
| AT-53 | Done (+ UUID serialization fix) | Unit + live persist pass | — |
| AT-56 | Done | `test_at56_*` + `test:at56` pass | Refresh smoke optional |
| AT-57 | Done (retry + durable stage checkpoints) | 22 `test_at57_*` tests + fixture E2E pass | Explicit `SLIDE_VALIDATING` and `PREVIEW_RENDERING` resume proof added |

### What is **still left for Arvanit** (not “all done” until these)

1. **Formal ticket closure** — retain the proof in
   `docs/ARVANIT_DELIVERY_CHECKLIST.md` and attach it to the delivery record.
2. **Merge the 2026-09-03 hardening patch** — fixture-gate environment isolation
   and AT-57 late-stage checkpoint reuse.
3. **Optional live UI proof** — run the AT-47 browser smoke when the local web,
   API, worker and LLM account are available.
4. **Do NOT own:** ongoing layout/content quality or BT/JJ/MS product UX.

### Verdict

**AT implementation work for the nine continuation-plan tickets is complete and
has automated plus live Supabase proof.**  
**The merged team now includes BT-27 and the JJ/MS continuation work; final
release status still requires the complete gate and any required live smoke.**  
**Arvanit's next proposed scope (client pack, RAG, Gamma and filing) is not part
of this confirmed backlog; see `docs/ARVANIT_DELIVERY_CHECKLIST.md`.**

---

## 11. Verification commands

### AT-only bundle (use while JJ-22 blocks full gate)

```powershell
py -3 -m pytest tests/unit/api/test_at41_framework_render.py tests/unit/api/test_at56_job_reconnection.py tests/unit/api/test_at57_job_retry.py tests/unit/validation/test_compression_retry.py tests/unit/api/test_transcripts.py tests/unit/observability/test_at53_llm_logger.py tests/unit/api/test_frameworks.py tests/unit/api/test_at37_migration_verification.py tests/unit/api/test_es4_opportunity_pii.py -v

npm run test:at47 --workspace borek-web
npm run test:at56 --workspace borek-web
npm run test:at57 --workspace borek-web

$env:RUN_SUPABASE_INTEGRATION = "1"
py -3 scripts/verify_db.py
py -3 -m pytest tests/integration/api/test_at38_rls_isolation.py tests/integration/api/test_at53_llm_calls_persist.py -v
```

### Full client delivery gate (includes JJ-22 — currently fails)

```powershell
py -3 scripts/validate_all.py
```

### Database migrations (AT-37)

```powershell
py -3 scripts/apply_migrations.py
py -3 scripts/apply_migrations.py --reapply
py -3 scripts/verify_db.py
```

See also: `docs/database_migration_verification.md`.

---

## 12. Known live blockers (not AT)

| Symptom | Owner | Ticket | Action |
|---------|-------|--------|--------|
| `COVER_01 statBadges item count 4 exceeds maximum 3` | Blenard | BT-9, BT-15 | Fix live COVER_01 generator/prompt; max 3 badges |
| `timeline_01.png` golden color mismatch (1344 px) | Jaya | JJ-22 | Fix TIMELINE renderer or update approved golden |
| Manual Plan → Deck steps | Blenard | BT-25 | Auto chain after Approve |
| Raw errors in Deck center | Mayank | MS-25 | Customer-facing VALIDATION_NEEDS_REVIEW |
| EXECUTIVE_SUMMARY_01 stub | Jaya | JJ-23 | Full layout end-to-end |

---

*End of document. When returning: read §10 for AT status, §12 for blockers, run §11 proofs, then proceed with AT PR or coordinate BT/JJ fixes for live E2E.*
