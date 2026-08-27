# AT Platform Progress — Full Implementation Context

**Owner:** Arvanit Telaku (AT-1..AT-55)  
**Branch:** `arvanit`  
**Last updated:** August 2026  
**Gate command:** `py -3 scripts/validate_all.py` (must pass before marking tickets done)

This document gives any AI assistant or developer **complete context** on what Arvanit has built, where it lives, how it is tested, and what remains.

**For full AI/Claude handoff (all 55 tickets, architecture, conventions, run commands):** see [`docs/AI_ASSISTANT_HANDOFF.md`](./AI_ASSISTANT_HANDOFF.md).

---

## 1. Project role (platform spine)

Arvanit owns the **platform spine** — not AI prompting (Endrit ES-*), not layout-specific slide content/renderers (Blenard BT-*, Jaya JJ-*, Mayank MS-*). Frontend UI started at **AT-46** (upload); framework review and deck UI remain AT-47+.

| Arvanit builds | Others build on it |
|---|---|
| JSON Schema contracts (`packages/contracts/`) | Endrit: FrameworkObject LLM output |
| Pydantic + TypeScript codegen | All teams import generated types |
| Generic validation + compression | BT/JJ/MS register per-layout limits |
| Borek Design System (tokens, masters, 14 components) | BT/JJ/MS implement 14 `renderXxx()` functions |
| Renderer dispatcher skeleton | BT/JJ/MS replace layout stubs |
| FastAPI platform, Supabase, auth, jobs | Endrit/Blenard wire real generation behind stubs |
| Next.js UI shell (AT-46+) | — |

Ownership boundaries: `docs/SCOPE.md`.

---

## 2. Pipeline overview

```
Opportunity
  └── Transcript(s)                    [ES-* Endrit]
        └── Knowledge Model
              └── FrameworkObject      [ES-9; schema AT-1]
                    └── (human confirm)
                          └── PresentationPlan   [BT-1; schema AT-2]
                                └── SlideSpecs   [BT/JJ/MS; base AT-3]
                                      └── PresentationVersion (.pptx + .pdf)
                                            [Renderer Node/TS; AT-7+ design system]
```

**Two runtimes:** Python (API validation, worker orchestration) + Node/TypeScript (PPTX generation, preview).

---

## 3. Completed tickets (AT-1 → AT-55)

### Contracts & codegen (AT-1..AT-6) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-1 | FrameworkObject schema (14 chapters) | `packages/contracts/framework_object.schema.json` |
| AT-2 | PresentationPlan schema | `packages/contracts/presentation_plan.schema.json` |
| AT-3 | SlideSpec base schema | `packages/contracts/slide_spec/base.schema.json` |
| AT-4 | Python Pydantic codegen | `scripts/generate_pydantic.py` → `generated/python/contracts/` |
| AT-5 | TypeScript codegen | `scripts/generate_typescript.js` → `generated/typescript/contracts/` |
| AT-6 | Schema consumers (version check, additive fields) | `packages/contracts/schema_consumer.py` |

Registries: `chapter_registry.json`, `layout_registry.json` (15 layouts).

---

### Validation & preview (AT-7..AT-10) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-7 | SlideSpec constraint validator | `apps/api/services/validation/` |
| AT-8 | Compression/retry orchestration | `apps/api/services/validation/` |
| AT-9 | LibreOffice preview pipeline (PPTX→PDF→PNG) | `apps/renderer/validation/libreoffice_pipeline.ts` |
| AT-10 | Render checks (spacing, fonts, alignment, color) | `apps/renderer/validation/render_checks.ts` |

---

### Design system (AT-11..AT-33) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-11..13 | Tokens: colors, typography, borders, branding, spacing, grid | `apps/renderer/design_system/tokens/` |

**Requirement status tokens (BT-8 / BT-21 support):** `BorekRequirementStatusColors` + `resolveRequirementStatusColors()` in `tokens/colors.ts` and `tokens/requirement_status.ts`. Maps `included | partial | later` to fill/text/border hex derived from brand tokens. SlideSpec never carries colors.
| AT-14..18 | Slide masters: DEFAULT, COVER, SECTION, CONTENT, CLOSING | `apps/renderer/design_system/masters/` |
| AT-19..32 | 14 shared components (title, footer, KPI card, chart, timeline, etc.) | `apps/renderer/design_system/components/` |
| AT-33 | Layout dispatcher — `layoutId` → render fn registry (stubs for all 15 layouts) | `apps/renderer/layouts/dispatcher.ts` |

BT/JJ/MS replace individual stubs in `apps/renderer/layouts/stubs.ts` without changing dispatcher routing.

---

### API platform (AT-34..AT-45) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-34 | FastAPI app, error format, CORS, config | `apps/services/api/app/main.py`, `middleware/error_handler.py` |
| AT-35 | Celery + Redis worker wiring | `apps/services/api/app/worker.py` |
| AT-36 | Job stage state machine (§24 pipeline stages) | `apps/services/api/app/services/job_service.py`, `schemas/jobs.py` |
| AT-37 | Supabase schema — 11 migrations, 10 tables | `apps/services/api/supabase/migrations/001..011` |
| AT-38 | Row Level Security policies | `011_rls_policies.sql` |
| AT-39 | Supabase JWT auth (JWKS ES256 prod, HS256 test tokens) | `apps/services/api/app/auth.py` |
| AT-40 | Opportunity + transcript endpoints (§22.1) | `routers/opportunities.py`, `routers/transcripts.py` |
| AT-41 | Framework endpoints (§22.2) + Endrit stub | `routers/frameworks.py`, `services/framework_generation.py` |
| AT-42 | Presentation-plan generate (§22.3) + Blenard stub | `routers/presentations.py`, `services/presentation_generation.py` |
| AT-43 | Presentation generate — rejects non-confirmed framework | same |
| AT-44 | Slide regenerate + change-layout (§22.4) | same + slide data layer |
| AT-45 | Job status endpoint — stage, status, structured errors, ownership | `routers/jobs.py` |

---

### Frontend (AT-46) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-46 | Next.js upload UI — multi-file, per-file status, client-side format reject | `apps/web/src/app/upload/`, `src/components/TranscriptUploadPanel.tsx`, `src/lib/transcriptFormats.ts`, `src/lib/uploadQueue.ts` |

**Stack:** Next.js 15 App Router, React 19, TypeScript.

**Done-when met:**
- Multi-file picker + drag-and-drop
- Per-file status: `rejected | pending | uploading | success | error`
- Invalid extensions (not `.txt`, `.vtt`, `.srt`, `.docx`) rejected **before** any API call
- Wires `POST /opportunities` then `POST /opportunities/{id}/transcripts` with bearer token

**Tests:** `npm run test:at46 --workspace borek-web`; `npm run typecheck --workspace borek-web`.

**Run locally:** `npm.cmd run dev --workspace borek-web` → http://localhost:3000/upload

### Frontend (AT-47) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-47 | Framework review/edit UI — 14 chapters, visible source_refs, inline edit persists | `apps/web/src/app/framework-review/`, `src/components/FrameworkReviewPanel.tsx`, `FrameworkChapterView.tsx`, `SourceRefBadge.tsx`, `src/lib/frameworkEdit.ts` |

**AT-47 API addition:** `PATCH /opportunities/{id}/framework` persists draft edits (depends on AT-41).

**Tests:** `npm run test:at47 --workspace borek-web`; framework PATCH covered in `tests/unit/api/test_frameworks.py`.

### Frontend (AT-48) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-48 | Presentation plan preview UI — slide list (order, purpose, layout) before full generation | `apps/web/src/app/plan-preview/`, `src/components/PlanPreviewPanel.tsx`, `src/lib/planPreview.ts`, `src/lib/planTypes.ts` |

**Depends on AT-42:** `GET /opportunities/{id}/presentation-plan`, `POST /opportunities/{id}/presentation-plan/generate`.

**Done-when met:**
- Planned slide list shows **order**, **purpose**, and **layout** (`layoutId`) for every slide
- User can generate and review the plan before full deck generation (AT-43)
- Requires confirmed framework (matches API guard)

**Tests:** `npm run test:at48 --workspace borek-web`; plan API covered in `tests/unit/api/test_presentations.py`.

### Frontend (AT-49) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-49 | Slide preview/download center — per-slide PNG preview, `.pptx`/`.pdf` downloads | `apps/web/src/app/deck-center/`, `src/components/DeckCenterPanel.tsx`, `SlidePreviewCard.tsx`, `src/lib/deckCenter.ts` |

**Depends on AT-44 + AT-9:** slide list/regenerate API (AT-44); preview PNG/PDF artifacts (AT-9 stubbed locally via `deck_assets.py`).

**API additions:** `GET /opportunities/{id}/presentation`, `GET /presentations/{id}/deck`, `GET /presentations/{id}/preview/slides/{index}.png`, `GET /presentations/{id}/download/pptx|pdf`.

**Done-when met:**
- Rendered preview images display **per slide**
- `.pptx` and `.pdf` **download links work** (authenticated blob download in UI)

**Tests:** `npm run test:at49 --workspace borek-web`; deck endpoints in `tests/unit/api/test_presentations.py` (`test_deck_center_preview_and_downloads`).

### DevOps (AT-50) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-50 | Docker Compose full stack | `docker-compose.yml`, `docker/api|worker|renderer|web/Dockerfile`, `apps/renderer/server.ts` |

**Done-when met:**
- `docker compose up --build` brings up **web**, **api**, **worker**, **renderer**, **redis**
- Internal service wiring via `REDIS_URL` and `RENDERER_URL`
- Supabase + LLM credentials loaded from root `.env` only

**Run stack:**
```powershell
copy .env.example .env
docker compose up --build
```

**Tests:** `tests/unit/devops/test_at50_compose.py`.

### DevOps (AT-51) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-51 | Complete `.env.example` — every stack env var with one-line description | `.env.example`, `apps/web/.env.local.example`, `tests/unit/devops/test_at51_env_example.py` |

**Done-when met:**
- Every environment variable used across API, worker, web, renderer, Docker Compose, and dev scripts is listed in root `.env.example`
- Each variable has a one-line `#` description immediately above its assignment

**Tests:** `tests/unit/devops/test_at51_env_example.py` (canonical var set + description contract).

**Depends on:** AT-50 (compose defines publish-port and service wiring vars).

### Platform (AT-52) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-52 | Audit log infra on state-changing endpoints — shared utility records actor + action + timestamp | `app/services/audit/audit_log.py`, router wiring, `memory_store.py` / `supabase_store.py` `append_audit_log`, `tests/unit/api/test_at52_audit_log.py` |

**Done-when met:**
- Shared `record_audit_event()` utility persists `actor_id`, `action`, `object_type`, `object_id`, and `timestamp` to `audit_log`
- Used by every state-changing endpoint: create/update opportunity, transcript upload/regenerate, framework generate/regenerate-chapter/confirm/update/render, presentation plan generate, presentation generate, slide regenerate, slide change-layout

**Tests:** `tests/unit/api/test_at52_audit_log.py`.

**Depends on:** AT-37 (`audit_log` table + migration 010).

### Platform (AT-53) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-53 | AI observability logging — every LLM call logs metadata without confidential content | `apps/api/services/observability/llm_logger.py`, `apps/api/llm/client.py`, `tests/unit/observability/test_at53_llm_logger.py` |

**Done-when met:**
- Shared `log_llm_call()` / `invoke_llm()` utility records **request id**, **stage**, **model**, **prompt version**, **token counts**, **latency**, and **retry count**
- Stages covered: **framework**, **planning**, **slide generation**, **compression**
- Confidential payload fields (`prompt`, `messages`, `content`, etc.) are rejected — no full prompt/response bodies logged
- `LlmClient` routes all four pipeline LLM entry points through the logger

**Tests:** `tests/unit/observability/test_at53_llm_logger.py`.

**Depends on:** AT-34 (server-side API platform).

### Integration (AT-54) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-54 | Full pipeline integration harness — fixture transcript through upload → confirm → plan → slides → pptx | `tests/integration/full_pipeline/harness.py`, `tests/integration/full_pipeline/test_at54_full_pipeline.py`, `tests/fixtures/transcripts/discovery_call.minimal.txt` |

**Done-when met:**
- Checked-in fixture transcript (`tests/fixtures/transcripts/discovery_call.minimal.txt`)
- One automated test runs the entire pipeline: **upload** → **confirm** → **plan** → **slides** → **pptx**
- Reusable `run_full_pipeline()` harness for future ES-33 fixture swaps

**Tests:** `tests/integration/full_pipeline/test_at54_full_pipeline.py` (wired in `scripts/validate_all.py`).

**Depends on:** AT-41..AT-44 (API endpoints); uses platform stubs until ES-33 eval fixtures land.

### Renderer QA (AT-55) — DONE

| Ticket | Deliverable | Key paths |
|--------|-------------|-----------|
| AT-55 | Golden-deck regression runner — rendered PNGs vs approved reference; flags spacing/font/alignment/color diffs | `tests/golden_deck/compare.ts`, `run_regression.ts`, `reference/slide-01.png`, `tests/golden_deck/run_regression.test.ts`, `tests/unit/renderer/test_at55_golden_deck.py` |

**Done-when met:**
- Approved reference rendering checked in under `tests/golden_deck/reference/`
- `run_regression.ts` renders a test deck via AT-9 (or compares `--actual` PNG dir) and diffs against reference
- Comparison reports **spacing**, **font**, **alignment**, and **color** differences

**Tests:** `npm run test:at55 --workspace borek-renderer`; `tests/unit/renderer/test_at55_golden_deck.py`; wired in `scripts/validate_all.py`.

**Depends on:** AT-9 (preview pipeline), AT-33 (layout dispatcher / renderer stack).

---

All routes except `GET /health` require `Authorization: Bearer <jwt>`.

### Health
- `GET /health` → `{"status": "ok"}`

### Opportunities (AT-40)
- `POST /opportunities` — create
- `GET /opportunities` — list (scoped to user)
- `GET /opportunities/{id}` — get
- `PATCH /opportunities/{id}` — update

### Transcripts (AT-40)
- `POST /opportunities/{id}/transcripts` — upload (.txt, .vtt, .srt, .docx)
- `GET /opportunities/{id}/transcripts` — list
- `GET /opportunities/{id}/transcripts/{transcript_id}` — get
- `POST /opportunities/{id}/transcripts/{transcript_id}/regenerate` — reset processing

### Frameworks (AT-41)
- `POST /opportunities/{id}/framework/generate` → 202 + job + framework_version_id
- `POST /opportunities/{id}/framework/regenerate-chapter` → 202 + job
- `POST /opportunities/{id}/framework/confirm` → confirmed framework
- `POST /opportunities/{id}/framework/render` → 202 (requires confirmed)
- `GET /opportunities/{id}/framework` — latest version
- `GET /frameworks/{framework_version_id}` — by id

### Presentations (AT-42..AT-44)
- `POST /opportunities/{id}/presentation-plan/generate` → 202 (requires confirmed framework)
- `GET /opportunities/{id}/presentation-plan` — latest plan
- `GET /presentation-plans/{id}` — plan by id
- `POST /opportunities/{id}/presentation/generate` → 202 (requires plan; creates version + slides stub)
- `GET /presentations` — list
- `GET /presentations/{id}` — get
- `GET /presentations/{id}/slides` — list slides in latest version
- `GET /presentations/{id}/slides/{slide_id}` — get slide
- `GET /presentations/{id}/deck` — deck center manifest (preview + download URLs)
- `GET /presentations/{id}/preview/slides/{slide_index}.png` — slide preview image
- `GET /presentations/{id}/download/pptx` — download deck
- `GET /presentations/{id}/download/pdf` — download PDF
- `GET /opportunities/{id}/presentation` — latest presentation for opportunity
- `POST /presentations/{id}/slides/{slide_id}/regenerate` → 202, job_type `slide_regenerate`
- `POST /presentations/{id}/slides/{slide_id}/change-layout` → 202, job_type `slide_change_layout` (body: `{layout_id}`)

### Jobs (AT-45)
- `GET /jobs/{job_id}` — status, current_stage, structured error on failure (ownership via opportunity RLS)
- `POST /jobs/health-check` — Celery wiring test (dev)

---

## 5. Data layer architecture

**Factory:** `app/services/data/__init__.py` → `build_data_store(token)`

| Backend | When | Implementation |
|---------|------|----------------|
| `memory` | Unit tests (`API_DATA_BACKEND=memory` in conftest) | `memory_store.py` |
| `supabase` | Production (`API_DATA_BACKEND=supabase`) | `supabase_store.py` — PostgREST with caller JWT for RLS |

**Dependency injection:** `DataStoreDep` in `app/dependencies.py`.

Legacy `get_db_session()` still returns 501 — AT-40+ routes use data store, not SQLAlchemy directly.

---

## 6. Integration stubs (for other developers)

| Stub | Wired for | Fixture used |
|------|-----------|--------------|
| `framework_generation.py` | Endrit ES-9/ES-12 | `packages/contracts/fixtures/framework_object.minimal.json` |
| `presentation_generation.py` | Blenard BT-1 (plan) | `packages/contracts/fixtures/presentation_plan.minimal.json` |
| Slide stubs on presentation generate | BT/JJ/MS content gen | Built from plan slides with minimal SlideSpec shape |
| Layout dispatcher stubs | BT/JJ/MS renderers | `apps/renderer/layouts/stubs.ts` |

Job types enqueued: `framework_generation`, `framework_regenerate_chapter`, `framework_render`, `presentation_planning`, `presentation_generation`, `slide_regenerate`, `slide_change_layout`.

---

## 7. Database tables (migrations 001–011)

1. `opportunities`
2. `transcripts`
3. `transcript_sections`
4. `framework_versions`
5. `presentation_plans`
6. `presentations`
7. `presentation_versions`
8. `slides`
9. `generation_jobs`
10. `audit_log`

All tables have RLS policies scoped via `auth.uid()` → opportunity ownership chain.

---

## 8. Auth & environment

**Auth:** `app/auth.py` — verifies Supabase JWT via JWKS (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`) for ES256; unit tests use HS256 via `SUPABASE_JWT_SECRET`.

**Required env vars:** see `apps/services/api/app/config.py` and `.env.example`.

**DB note:** Direct Postgres to Supabase may fail on IPv6-only networks; REST API verification via `scripts/verify_db.py` works with `SUPABASE_SERVICE_ROLE_KEY`.

---

## 9. Test inventory (API unit tests)

Located in `tests/unit/api/`:

| File | Covers |
|------|--------|
| `test_opportunities.py` | AT-40 |
| `test_transcripts.py` | AT-40 |
| `test_frameworks.py` | AT-41 |
| `test_presentations.py` | AT-42, AT-43 |
| `test_slide_endpoints.py` | AT-44 |
| `test_jobs.py` | AT-45 |
| `test_at52_audit_log.py` | AT-52 |
| `tests/unit/observability/test_at53_llm_logger.py` | AT-53 |
| `tests/integration/full_pipeline/test_at54_full_pipeline.py` | AT-54 |
| `tests/unit/renderer/test_at55_golden_deck.py` | AT-55 |
| `test_job_stage_machine.py` | AT-36 |
| `test_auth.py`, `test_auth_required.py` | AT-39 |
| `test_migrations.py`, `test_rls_policies.py` | AT-37, AT-38 |

Contract tests: `tests/unit/contracts/` (AT-1..6).  
Renderer tests: `tests/unit/renderer/` + npm workspace scripts (AT-9..33).

---

## 10. Error response format

All API errors:

```json
{
  "error": {
    "code": "OPPORTUNITY_NOT_FOUND",
    "message": "Human readable message",
    "detail": {}
  }
}
```

Common codes: `FRAMEWORK_NOT_CONFIRMED`, `PRESENTATION_PLAN_NOT_FOUND`, `SLIDE_NOT_FOUND`, `JOB_NOT_FOUND`, `UNAUTHORIZED`.

---

## 11. Not yet implemented (Arvanit backlog)

_All AT-1..AT-55 platform tickets complete._

---

## 12. Key conventions for continuing work

1. **Match AT-41 pattern** for new endpoints: schema → service stub → data store (memory + supabase) → router → unit tests → gate.
2. **Do not hand-edit** `generated/python/` or `generated/typescript/`.
3. **Job enqueue** via `job_service.create_job(opportunity_id, job_type, presentation_id=...)`.
4. **Confirmed framework gate** for all presentation operations after framework stage.
5. **Commit rhythm:** batch every ~3 tickets (team agreement).
6. **Run gate** before marking any ticket done: `py -3 scripts/validate_all.py`.

---

## 13. File map (API — most active area)

```
apps/services/api/
├── app/
│   ├── main.py                 # Router registration
│   ├── auth.py                 # JWT verification
│   ├── config.py               # Env settings
│   ├── dependencies.py         # DataStoreDep, AuthUserDep
│   ├── routers/
│   │   ├── health.py
│   │   ├── opportunities.py    # AT-40
│   │   ├── transcripts.py      # AT-40
│   │   ├── frameworks.py       # AT-41
│   │   ├── presentations.py    # AT-42..44
│   │   └── jobs.py             # AT-45
│   ├── schemas/                # Pydantic request/response models
│   └── services/
│       ├── framework_generation.py      # Endrit stub
│       ├── presentation_generation.py   # Blenard + slide stubs
│       ├── job_service.py               # In-memory job store (AT-36)
│       └── data/
│           ├── memory_store.py          # Unit test backend
│           └── supabase_store.py        # PostgREST backend
└── supabase/migrations/        # 001..011
```

---

*End of AT progress context document.*

---

## 14. File map (web — AT-46+)

```
apps/web/
├── package.json              # Next.js 15, test:at46, typecheck
├── next.config.ts
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx            # redirects to /upload
│   │   ├── login/page.tsx      # AT-39 sign-in
│   │   ├── register/page.tsx   # AT-39 registration
│   │   ├── upload/page.tsx     # AT-46
│   │   └── framework-review/page.tsx  # AT-47
│   ├── components/
│   │   ├── AuthProvider.tsx
│   │   ├── AuthShell.tsx
│   │   ├── AuthCard.tsx        # shared sign-in / register form
│   │   ├── SiteHeader.tsx
│   │   ├── OpportunityForm.tsx
│   │   ├── FileUploadQueue.tsx
│   │   └── TranscriptUploadPanel.tsx
│   │   ├── FrameworkReviewPanel.tsx
│   │   ├── FrameworkChapterView.tsx
│   │   └── SourceRefBadge.tsx
│   └── lib/
│       ├── api.ts              # opportunities + transcript upload client
│       ├── supabase.ts
│       ├── transcriptFormats.ts
│       ├── uploadQueue.ts
│       ├── frameworkTypes.ts
│       └── frameworkEdit.ts
```
