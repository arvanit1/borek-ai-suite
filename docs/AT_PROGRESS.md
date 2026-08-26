# AT Platform Progress — Full Implementation Context

**Owner:** Arvanit Telaku (AT-1..AT-55)  
**Branch:** `arvanit`  
**Last updated:** August 2026  
**Gate command:** `py -3 scripts/validate_all.py` (must pass before marking tickets done)

This document gives any AI assistant or developer **complete context** on what Arvanit has built, where it lives, how it is tested, and what remains.

---

## 1. Project role (platform spine)

Arvanit owns the **platform spine** — not AI prompting (Endrit ES-*), not layout-specific slide content/renderers (Blenard BT-*, Jaya JJ-*, Mayank MS-*), not frontend UI until AT-46+.

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

## 3. Completed tickets (AT-1 → AT-45)

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

## 4. Live API endpoints (as of AT-45)

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

| Ticket | Title | Notes |
|--------|-------|-------|
| AT-46 | Next.js upload UI | Depends on AT-40 |
| AT-47 | Framework review/edit UI | Depends on AT-41 |
| AT-48 | Presentation plan preview UI | Depends on AT-42 |
| AT-49 | Slide preview/download center | Depends on AT-44, AT-9 |
| AT-50 | Docker Compose full stack | |
| AT-51 | `.env.example` completeness | |
| AT-52 | Audit log infra on state-changing endpoints | |
| AT-53 | AI observability logging | |
| AT-54 | Full pipeline integration test | Last — needs ES-33 + all layouts |
| AT-55 | Golden-deck regression runner | |

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
