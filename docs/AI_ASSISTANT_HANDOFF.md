# AI Assistant Handoff — Borek AI Suite (AT-1 → AT-55)

**Purpose:** Give Claude (or any AI coding assistant) **full context** on what was built, how it works, where code lives, and how to extend it safely.

**Owner:** Arvanit Telaku — platform spine tickets **AT-1 through AT-55**  
**Branch:** `arvanit`  
**Status:** All AT platform tickets **complete** (August 2026)  
**Living progress tracker:** [`docs/AT_PROGRESS.md`](./AT_PROGRESS.md)  
**Gate before marking work done:** `py -3 scripts/validate_all.py`

---

## How to use this document

1. **Read §1–2 first** — project boundaries and repo layout (two runtimes: Python API + Node renderer).
2. **Use §3 ticket index** — every AT ticket with Jira-style name, done-when, paths, tests, dependencies.
3. **Use §4–6** — end-to-end user/API flow, architecture, and integration stubs (what is real vs stubbed).
4. **Use §7–9** — frontend pages, env/run commands, testing strategy.
5. **Use §10–11** — conventions, gotchas, and what other developers (Endrit/Blenard/Jaya/Mayank) still wire in.

When implementing new work: **match existing patterns** (especially AT-41 for API endpoints). Do **not** hand-edit `generated/python/` or `generated/typescript/`.

---

## 1. What this project is

**Borek AI Suite** automates sales-engineering deliverables after client discovery calls:

| Input | Output |
|-------|--------|
| Meeting transcript(s) (`.txt`, `.vtt`, `.srt`, `.docx`) | **Framework Object** — 14-chapter structured proposal |
| Human-confirmed Framework Object | **Presentation deck** (`.pptx` + `.pdf` + slide PNG previews) |

**Core principle:** Presentations are generated **only** from the **human-confirmed** Framework Object — never re-read from raw transcript in later stages.

### Ownership boundaries

| Owner | Scope | Ticket prefix |
|-------|--------|---------------|
| **Arvanit** | Platform spine: schemas, codegen, validation, design system, renderer skeleton, FastAPI, Supabase, auth, jobs, Next.js shell, DevOps, audit/observability, integration tests | **AT-*** |
| **Endrit** | Transcript → Knowledge Model → Framework synthesis (Claude) | **ES-*** |
| **Blenard** | Group A layouts + presentation planner | **BT-*** |
| **Jaya** | Group B layouts | **JJ-*** |
| **Mayank** | Group C layouts | **MS-*** |

See also: `docs/SCOPE.md`, `README.md`.

---

## 2. Repository layout (mental model)

```
borek-ai-suite/
├── packages/contracts/          # JSON Schema SSOT (AT-1..3)
├── generated/python|typescript/ # Codegen output — DO NOT hand-edit (AT-4, AT-5)
├── apps/
│   ├── api/                     # Shared Python services (validation AT-7/8, slide gen stubs)
│   ├── services/api/            # FastAPI platform (AT-34+) — main HTTP API
│   ├── worker/                  # Celery task wrappers
│   ├── renderer/                # Node/TS PPTX + design system (AT-9..33)
│   └── web/                     # Next.js UI (AT-46..49)
├── tests/
│   ├── unit/                    # Primary test suite (pytest)
│   ├── integration/full_pipeline/  # AT-54 harness
│   └── golden_deck/             # AT-55 regression runner
├── scripts/validate_all.py      # Delivery gate
├── docker-compose.yml           # AT-50 full stack
└── .env.example                 # AT-51 canonical env documentation
```

### Two runtimes

| Runtime | Language | Responsibility |
|---------|----------|----------------|
| **API / worker** | Python 3.12+ | HTTP API, auth, data store, job state machine, validation orchestration |
| **Renderer** | Node 20+ / TypeScript | PPTX generation, Borek design system, LibreOffice preview pipeline |

`pyproject.toml` adds both `apps/api` and `apps/services/api` to `pythonpath`.

---

## 3. Complete ticket reference (AT-1 → AT-55)

Each row: **Jira-style name**, **done-when summary**, **key paths**, **tests**, **depends on**.

### Phase 1 — Contracts & codegen (AT-1..AT-6)

| Ticket | Jira name | Done when | Key paths | Tests |
|--------|-----------|-----------|-----------|-------|
| AT-1 | Define FrameworkObject JSON Schema | 14 chapters, quality scores, source_refs in SSOT schema | `packages/contracts/framework_object.schema.json` | `tests/unit/contracts/` |
| AT-2 | Define PresentationPlan JSON Schema | Slide order, purpose, layoutId per slide | `packages/contracts/presentation_plan.schema.json` | same |
| AT-3 | Define SlideSpec base schema | Shared SlideSpec fields incl. sourceChapterIds | `packages/contracts/slide_spec/base.schema.json` + per-layout schemas | same |
| AT-4 | Python Pydantic codegen | Generated models importable from `generated/python/contracts/` | `scripts/generate_pydantic.py` | gate import check |
| AT-5 | TypeScript codegen | Generated types in `generated/typescript/contracts/` | `scripts/generate_typescript.js` | gate file existence |
| AT-6 | Schema consumer utilities | Version mismatch errors; additive field tolerance | `packages/contracts/schema_consumer.py` | `tests/unit/contracts/test_schema_consumer.py` |

**Registries:** `layout_registry.json` (15 layouts), `chapter_registry.json`, `chapter_layout_map.json`, `constraints/group_*.yaml`.

---

### Phase 2 — Validation & preview (AT-7..AT-10)

| Ticket | Jira name | Done when | Key paths | Tests |
|--------|-----------|-----------|-----------|-------|
| AT-7 | Build SlideSpec constraint validator | Generic required/type/count/max_length checks per layout | `apps/api/services/validation/constraint_validator.py` | `tests/unit/validation/` |
| AT-8 | Build compression/retry orchestration | Up to 2 AI-shortening passes; revalidate after each | `apps/api/services/validation/compression_retry.py` | `tests/unit/validation/test_compression_retry.py` |
| AT-9 | Build LibreOffice preview pipeline | `.pptx` → `.pdf` + per-slide `.png` | `apps/renderer/validation/libreoffice_pipeline.ts`, `scripts/run_preview_pipeline.ts` | `npm run test:at9`, `tests/unit/renderer/test_libreoffice_pipeline.py` |
| AT-10 | Build render validation checks | Slide count, blank slide, artifact sanity after AT-9 | `apps/renderer/validation/render_checks.ts` | `npm run test:at10` |

---

### Phase 3 — Design system & dispatcher (AT-11..AT-33)

| Ticket | Jira name | Done when | Key paths | Tests |
|--------|-----------|-----------|-----------|-------|
| AT-11 | Brand color tokens | All brand hex via named tokens | `apps/renderer/design_system/tokens/colors.ts` | `npm run test:at11` |
| AT-12 | Typography tokens | Named font sizes/roles | `tokens/typography.ts` | `npm run test:at12` |
| AT-13 | Spacing tokens | Consistent spacing scale | `tokens/spacing.ts` | `npm run test:at13` |
| AT-14..18 | Slide masters | DEFAULT, COVER, SECTION, CONTENT, CLOSING | `design_system/masters/MASTER_*.ts` | `npm run test:at14..at18` |
| AT-19..32 | Shared components (14) | Title, footer, KPI card, chart, timeline, etc. | `design_system/components/add*.ts` | `npm run test:at19..at32` |
| AT-33 | Layout dispatcher | `layoutId` → render function registry; stubs for all 15 layouts | `apps/renderer/layouts/dispatcher.ts`, `layouts/stubs.ts` | `npm run test:at33` |

**Note:** BT/JJ/MS replace individual stubs in `layouts/stubs.ts` without changing dispatcher routing. Requirement status colors for matrix slides: `BorekRequirementStatusColors` in `colors.ts`.

Also: grid, borders, branding tokens with dedicated npm test scripts in `apps/renderer/package.json`.

---

### Phase 4 — API platform (AT-34..AT-45)

| Ticket | Jira name | Done when | Key paths | Tests |
|--------|-----------|-----------|-----------|-------|
| AT-34 | Bootstrap FastAPI application | App factory, CORS, consistent errors, config fail-fast | `apps/services/api/app/main.py`, `middleware/error_handler.py`, `config.py` | `tests/unit/api/test_health.py`, `test_error_format.py` |
| AT-35 | Wire Celery + Redis worker | Worker entrypoint; health-check task | `app/worker.py`, `apps/worker/` | `tests/integration/api/test_worker_wiring.py` (needs Redis) |
| AT-36 | Job stage state machine | QUEUED → … → COMPLETED/FAILED per §24 | `app/services/job_service.py`, `schemas/jobs.py` | `tests/unit/api/test_job_stage_machine.py` |
| AT-37 | Supabase schema migrations | 10 tables, migrations 001–010 | `supabase/migrations/001..010_*.sql` | `tests/unit/api/test_migrations.py` |
| AT-38 | Row Level Security policies | User-scoped access via opportunity ownership | `supabase/migrations/011_rls_policies.sql` | `tests/unit/api/test_rls_policies.py` |
| AT-39 | Supabase JWT auth | Bearer auth on all routes except `/health` | `app/auth.py` | `tests/unit/api/test_auth.py` |
| AT-40 | Build opportunity + transcript endpoints | §22.1 CRUD + upload | `routers/opportunities.py`, `routers/transcripts.py` | `test_opportunities.py`, `test_transcripts.py` |
| AT-41 | Build framework endpoints | generate/regenerate/confirm/render + Endrit stub | `routers/frameworks.py`, `services/framework_generation.py` | `test_frameworks.py` |
| AT-42 | Build presentation-plan generate | Plan stub (Blenard BT-1) | `routers/presentations.py`, `services/presentation_generation.py` | `test_presentations.py` |
| AT-43 | Build presentation generate | Requires confirmed framework; creates slides stub | same | same |
| AT-44 | Build slide regenerate + change-layout | §22.4 slide mutation endpoints | same + data layer slide methods | `test_slide_endpoints.py` |
| AT-45 | Build job status endpoint | Stage, status, structured error on failure | `routers/jobs.py` | `test_jobs.py` |

**Data layer pattern (critical):**

```
build_data_store(jwt) → MemoryDataStore (tests) | SupabaseDataStore (prod)
```

- Factory: `app/services/data/__init__.py`
- Memory: `memory_store.py` — used when `API_DATA_BACKEND=memory`
- Supabase: `supabase_store.py` — PostgREST with caller JWT for RLS
- Injection: `DataStoreDep`, `AuthUserDep` in `dependencies.py`
- Legacy `get_db_session()` returns **501** — do not use for new routes

---

### Phase 5 — Frontend (AT-46..AT-49)

| Ticket | Jira name | Done when | Key paths | Tests |
|--------|-----------|-----------|-----------|-------|
| AT-46 | Build transcript upload UI | Multi-file upload, per-file status, client-side format reject | `apps/web/src/app/upload/`, `TranscriptUploadPanel.tsx`, `transcriptFormats.ts`, `uploadQueue.ts` | `npm run test:at46` |
| AT-47 | Build framework review/edit UI | 14 chapters, source_refs visible, inline edit persists | `app/framework-review/`, `FrameworkReviewPanel.tsx`, `frameworkEdit.ts` | `npm run test:at47` |
| AT-48 | Build presentation plan preview UI | Slide list: order, purpose, layoutId before deck gen | `app/plan-preview/`, `PlanPreviewPanel.tsx`, `planPreview.ts` | `npm run test:at48` |
| AT-49 | Build slide preview/download center | Per-slide PNG preview; pptx/pdf download | `app/deck-center/`, `DeckCenterPanel.tsx`, `deckCenter.ts` | `npm run test:at49` |

**UI stack:** Next.js 15 App Router, React 19, TypeScript.

**Auth:** `/login`, `/register` — `AuthProvider` in root layout; Supabase session shared with API via Bearer token in `lib/api.ts`.

**Pipeline stepper:** Shared `PipelineStepper.tsx` on upload → framework-review → plan-preview → deck-center pages.

**Query param convention:** All post-upload pages use `?opportunityId=<uuid>`.

**Empty-state pattern:** Use helpers in `lib/apiErrors.ts` — `isMissingFrameworkError`, `isMissingPresentationPlanError`, `isMissingPresentationError` so 404 “not yet created” is not shown as a red error.

---

### Phase 6 — DevOps & platform infra (AT-50..AT-55)

| Ticket | Jira name | Done when | Key paths | Tests |
|--------|-----------|-----------|-----------|-------|
| AT-50 | Docker Compose for full stack | `docker compose up` → web, api, worker, renderer, redis | `docker-compose.yml`, `docker/*/Dockerfile`, `apps/renderer/server.ts` | `tests/unit/devops/test_at50_compose.py` |
| AT-51 | Write `.env.example` | Every stack env var with one-line `#` description | `.env.example`, `apps/web/.env.local.example` | `tests/unit/devops/test_at51_env_example.py` |
| AT-52 | Build audit log infra | Shared utility; every state-changing endpoint logs actor+action+timestamp | `app/services/audit/audit_log.py`, router wiring, `append_audit_log` on stores | `tests/unit/api/test_at52_audit_log.py` |
| AT-53 | Build AI observability logging | Every LLM call logs metadata (no confidential content) | `apps/api/services/observability/llm_logger.py`, `apps/api/llm/client.py` | `tests/unit/observability/test_at53_llm_logger.py` |
| AT-54 | Build integration test harness | Fixture transcript runs upload→confirm→plan→slides→pptx in one test | `tests/integration/full_pipeline/harness.py`, `tests/fixtures/transcripts/discovery_call.minimal.txt` | `tests/integration/full_pipeline/test_at54_full_pipeline.py` |
| AT-55 | Build golden-deck test runner | Rendered PNGs vs approved reference; spacing/font/alignment/color diffs | `tests/golden_deck/compare.ts`, `run_regression.ts`, `reference/slide-01.png` | `npm run test:at55`, `tests/unit/renderer/test_at55_golden_deck.py` |

---

## 4. End-to-end pipeline flow

### 4.1 User journey (UI — Steps 1–4)

```
Step 1  /upload?opportunityId=…        Upload transcripts, create opportunity
Step 2  /framework-review?…            Generate → edit → confirm framework
Step 3  /plan-preview?…                Generate → review presentation plan
Step 4  /deck-center?…                 Generate deck → PNG previews → pptx/pdf download
```

Navigation links connect steps via `PipelineStepper` and inline hrefs in each panel.

### 4.2 API sequence (happy path)

```
POST   /opportunities
POST   /opportunities/{id}/transcripts          # upload
POST   /opportunities/{id}/framework/generate   # 202 + job
POST   /opportunities/{id}/framework/confirm
POST   /opportunities/{id}/presentation-plan/generate  # 202
POST   /opportunities/{id}/presentation/generate       # 202 + slides stub
GET    /presentations/{id}/slides
GET    /presentations/{id}/download/pptx
```

AT-54 harness (`run_full_pipeline()`) automates this sequence in one pytest.

### 4.3 Job types enqueued (AT-36)

`framework_generation`, `framework_regenerate_chapter`, `framework_render`, `presentation_planning`, `presentation_generation`, `slide_regenerate`, `slide_change_layout`.

Job store is **in-memory** in `job_service.py` for unit tests; worker Celery tasks are separate (`apps/worker/`).

---

## 5. Architecture deep dives

### 5.1 API error format (all routes)

```json
{
  "error": {
    "code": "FRAMEWORK_NOT_CONFIRMED",
    "message": "Human readable message",
    "detail": {}
  }
}
```

Implemented in `app/middleware/error_handler.py`. Common codes: `OPPORTUNITY_NOT_FOUND`, `FRAMEWORK_NOT_CONFIRMED`, `PRESENTATION_PLAN_NOT_FOUND`, `SLIDE_NOT_FOUND`, `JOB_NOT_FOUND`, `UNAUTHORIZED`.

### 5.2 Auth (AT-39)

- **Production:** Verify Supabase JWT via JWKS (ES256) — `app/auth.py`
- **Unit tests:** HS256 tokens via `create_test_access_token()` + `SUPABASE_JWT_SECRET`
- **Clock skew:** 60s leeway on JWT validation
- All routes except `GET /health` require `Authorization: Bearer <token>`

### 5.3 Audit log (AT-52)

Table: `audit_log` (migration 010) — `actor_id`, `action`, `object_type`, `object_id`, `timestamp`.

Utility: `record_audit_event(store, actor_id, action, object_type, object_id)` in `app/services/audit/audit_log.py`.

Wired on **all 13 state-changing endpoints** (every POST/PATCH mutation in opportunities, transcripts, frameworks, presentations routers).

### 5.4 LLM observability (AT-53)

Utility: `log_llm_call()` / `invoke_llm()` in `apps/api/services/observability/llm_logger.py`.

Logs: request id, stage, model, prompt version, token counts, latency, retry count.

Stages: `framework`, `planning`, `slide_generation`, `compression`.

Entry point: `apps/api/llm/client.py` — `LlmClient` with methods for each stage. **Rejects** logging confidential fields (`prompt`, `messages`, `content`, etc.).

### 5.5 Deck assets stub (AT-49 / local dev)

`apps/services/api/app/services/deck_assets.py` materializes stub `.pptx`, `.pdf`, and per-slide `.png` under `tmp/deck_assets/` using `tests/fixtures/renderer/minimal.pptx`.

Used by `deck_center.py` for preview/download routes until real renderer integration completes.

### 5.6 Database (AT-37 / AT-38)

**10 tables** (migrations 001–010) + RLS policies (011):

`opportunities`, `transcripts`, `transcript_sections`, `framework_versions`, `presentation_plans`, `presentations`, `presentation_versions`, `slides`, `generation_jobs`, `audit_log`.

Verify: `py -3 scripts/verify_supabase_complete.py` (schema + live RLS negative test; requires `RUN_SUPABASE_INTEGRATION=1` and pooler credentials). Quick schema-only check: `py -3 scripts/verify_db.py`.

---

## 6. Integration stubs (what is NOT real yet)

Platform endpoints exist; **AI generation is stubbed** until other developers wire real LLM/render logic.

| Stub file | Stands in for | Fixture / behavior |
|-----------|---------------|-------------------|
| `services/framework_generation.py` | Endrit ES-9/ES-12 | Loads `packages/contracts/fixtures/framework_object.minimal.json` |
| `services/presentation_generation.py` | Blenard BT-1 plan + deck | Loads `presentation_plan.minimal.json`; builds minimal SlideSpecs from plan |
| `apps/renderer/layouts/stubs.ts` | BT/JJ/MS renderers | Placeholder render fns registered in dispatcher |
| `apps/api/llm/client.py` | OpenAI/Anthropic calls | Stub executor returning metadata-only results |
| `services/deck_assets.py` | Full PPTX render pipeline | Copies minimal.pptx + 1×1 PNG stubs |

**Confirmed framework gate:** Presentation plan/generate endpoints reject unless `framework_versions.status == "confirmed"`.

**Draft edit gate:** `PATCH /opportunities/{id}/framework` rejects edits on confirmed frameworks (`FRAMEWORK_IMMUTABLE` 409).

---

## 7. Frontend file map (AT-46..49)

```
apps/web/src/
├── app/
│   ├── upload/page.tsx              # AT-46
│   ├── framework-review/page.tsx    # AT-47
│   ├── plan-preview/page.tsx        # AT-48
│   ├── deck-center/page.tsx         # AT-49
│   ├── login/page.tsx               # AT-39
│   └── register/page.tsx
├── components/
│   ├── PipelineStepper.tsx          # Shared 4-step nav
│   ├── TranscriptUploadPanel.tsx
│   ├── FrameworkReviewPanel.tsx
│   ├── FrameworkChapterView.tsx
│   ├── SourceRefBadge.tsx
│   ├── PlanPreviewPanel.tsx
│   ├── DeckCenterPanel.tsx
│   └── SlidePreviewCard.tsx
└── lib/
    ├── api.ts                       # All API client calls + token resolution
    ├── apiErrors.ts                 # Empty-state vs real error helpers
    ├── supabase.ts
    ├── transcriptFormats.ts
    ├── uploadQueue.ts
    ├── frameworkEdit.ts / frameworkFieldEdit.ts
    ├── planPreview.ts / planTypes.ts
    └── deckCenter.ts
```

**Run web locally:**

```powershell
npm.cmd run dev --workspace borek-web
# → http://localhost:3000/upload
```

---

## 8. Environment & running locally

### 8.1 Setup

```powershell
copy .env.example .env
# Fill: SUPABASE_*, ANTHROPIC_API_KEY, OPENAI_API_KEY, DATABASE_URL, REDIS_URL, etc.
```

Canonical var list enforced by AT-51: see `.env.example` (31 vars) and `tests/unit/devops/test_at51_env_example.py`.

### 8.2 Run services

| Service | Command | Port |
|---------|---------|------|
| API | `cd apps/services/api && py -3 -m uvicorn app.main:app --reload --port 8000` | 8000 |
| Web | `npm run dev --workspace borek-web` | 3000 |
| Full stack | `docker compose up --build` | see compose publish ports |
| Gate | `py -3 scripts/validate_all.py` | — |

API reads root `.env` automatically regardless of cwd.

### 8.3 Key env vars

| Var | Purpose |
|-----|---------|
| `API_DATA_BACKEND` | `memory` (tests) or `supabase` (prod) |
| `SUPABASE_JWT_SECRET` | HS256 test tokens |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Auth + PostgREST |
| `NEXT_PUBLIC_API_URL` | Web → API (optional override) |
| `RENDERER_URL` | API/worker → renderer service |
| `REDIS_URL` | Celery broker |

---

## 9. Testing strategy

### 9.1 Delivery gate (`scripts/validate_all.py`)

Runs in order:

1. `pytest tests/unit -v`
2. `pytest tests/integration/full_pipeline -v` (AT-54)
3. Python + TypeScript codegen checks
4. `npm run typecheck` (renderer + web)
5. `npm run test:at46..at49` (web)
6. `npm run test:at9..at33`, `test:at55`, `test:bt18/19` (renderer)

**Must pass** before marking any ticket done.

### 9.2 Test backend defaults

`tests/unit/api/conftest.py` and `tests/integration/conftest.py` set `API_DATA_BACKEND=memory` and reset memory stores per test.

### 9.3 Integration tests requiring external services

| Test | Requires |
|------|----------|
| `tests/integration/api/test_worker_wiring.py` | Running Redis (`@pytest.mark.integration`) |
| `tests/integration/api/test_rls_negative.py` | `RUN_SUPABASE_INTEGRATION=1` + migrated Supabase — or run `scripts/verify_supabase_complete.py` |
| `tests/unit/renderer/test_libreoffice_pipeline.py` (E2E) | Local LibreOffice+pdftoppm **or** Docker (can flake on Docker Desktop) |

### 9.4 Per-ticket test quick reference

| Ticket | Primary test command |
|--------|---------------------|
| AT-46 | `npm run test:at46 --workspace borek-web` |
| AT-47 | `npm run test:at47 --workspace borek-web` |
| AT-48 | `npm run test:at48 --workspace borek-web` |
| AT-49 | `npm run test:at49 --workspace borek-web` |
| AT-50 | `pytest tests/unit/devops/test_at50_compose.py` |
| AT-51 | `pytest tests/unit/devops/test_at51_env_example.py` |
| AT-52 | `pytest tests/unit/api/test_at52_audit_log.py` |
| AT-53 | `pytest tests/unit/observability/test_at53_llm_logger.py` |
| AT-54 | `pytest tests/integration/full_pipeline/test_at54_full_pipeline.py` |
| AT-55 | `npm run test:at55 --workspace borek-renderer` |

---

## 10. Conventions for extending the codebase

1. **New API endpoint:** schema → service → `memory_store` + `supabase_store` → router → `record_audit_event` if state-changing → unit tests → gate.
2. **Never edit codegen output** — change JSON Schema, then run `scripts/generate_pydantic.py` and `scripts/generate_typescript.js`.
3. **Job enqueue:** `job_service.create_job(opportunity_id, job_type, presentation_id=...)`.
4. **Web empty states:** use `apiErrors.ts` helpers; don't treat 404 `FRAMEWORK_NOT_FOUND` as fatal error on first visit.
5. **UI pages:** follow `upload-page` + `upload-hero` + `upload-layout` + `PipelineStepper` + `upload-meta-card` pattern from AT-46+.
6. **LLM calls:** route through `LlmClient` / `invoke_llm()` so AT-53 observability applies.
7. **Renderer layouts:** register in dispatcher; implement render fn; add golden reference PNG when visual baseline needed.

---

## 11. Known gotchas

| Issue | Detail |
|-------|--------|
| Docker AT-9 E2E flake | `test_at9_pipeline_produces_pdf_and_per_slide_pngs` may fail if Docker build errors (`lease does not exist`). Install local LibreOffice + poppler to avoid Docker fallback. |
| IPv6 Supabase Postgres | Direct `DATABASE_URL` may fail on IPv6-only networks; use REST via `verify_db.py`. |
| JWT clock skew | Auth allows 60s leeway — see `auth.py`. |
| Memory vs Supabase | Unit tests never hit real Supabase unless explicitly integration-marked. |
| ES-33 fixtures | AT-54 uses `tests/fixtures/transcripts/discovery_call.minimal.txt`; swap for ES-33 eval fixtures when available. |

---

## 12. What other teams still implement

| Team | Work | Builds on |
|------|------|-----------|
| Endrit (ES-*) | Real transcript extraction + framework synthesis | AT-1 schema, AT-41 endpoints, AT-53 logging |
| Blenard (BT-*) | Presentation planner, Group A content + renderers | AT-2/3 schemas, AT-42/44, dispatcher stubs |
| Jaya (JJ-*) | Group B content + renderers | Same pattern |
| Mayank (MS-*) | Group C content + renderers | Same pattern |

When wiring real generation: replace stub service functions **inside** `framework_generation.py` / `presentation_generation.py` — keep router and data-store contracts stable.

---

## 13. Quick API reference (all routes)

See **§4.2** and full listing in [`docs/AT_PROGRESS.md` §4](./AT_PROGRESS.md#4-live-api-endpoints-as-of-at-45).

Router registration: `apps/services/api/app/main.py`.

---

## 14. Related documents

| Document | Use for |
|----------|---------|
| [`docs/AT_PROGRESS.md`](./AT_PROGRESS.md) | Ticket status, done-when notes, file maps |
| [`docs/SCOPE.md`](./SCOPE.md) | Team ownership boundaries |
| [`docs/IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) | Detailed AT-7–10 validation reference |
| [`docs/TEAM_HANDOFF_AT7-9.md`](./TEAM_HANDOFF_AT7-9.md) | Validation pipeline handoff |
| [`README.md`](../README.md) | Full repo tree aligned to backlog |
| [`.env.example`](../.env.example) | All environment variables (AT-51) |

---

*This document describes the complete AT-1..AT-55 platform spine as implemented on branch `arvanit`. Update it when adding new platform capabilities.*
