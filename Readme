borek-ai-suite/                            # Framework & Presentation Generation Pipeline
                                           # Aligned to Development Task Backlog v1.0 (Aug 2026)

├── README.md

├── .env.example                           # AT-51 — every env var documented

├── docker-compose.yml                     # AT-50 — web / api / worker / renderer / redis

├── pyproject.toml

│

├── packages/

│   └── contracts/                         # AT-1, AT-2, AT-3 — canonical JSON Schema (SSOT)

│       ├── framework_object.schema.json   # AT-1 — 14 chapters, quality scores, source_refs

│       ├── knowledge_model.schema.json    # ES-5 — facts, constraints, risks, unknowns

│       ├── presentation_plan.schema.json  # AT-2 — slide order, purpose, layoutId, frameworkRefs

│       ├── slide_spec/

│       │   ├── base.schema.json           # AT-3 — shared fields incl. sourceChapterIds

│       │   │

│       │   ├── group_a/                   # Blenard — BT-4..BT-8

│       │   │   ├── cover_01.schema.json

│       │   │   ├── context_01.schema.json

│       │   │   ├── problem_solution_01.schema.json

│       │   │   ├── scope_01.schema.json

│       │   │   └── requirements_matrix_01.schema.json

│       │   │

│       │   ├── group_b/                   # Jaya — JJ-1..JJ-4

│       │   │   ├── process_flow_01.schema.json

│       │   │   ├── timeline_01.schema.json

│       │   │   ├── milestones_01.schema.json

│       │   │   └── team_fte_01.schema.json

│       │   │

│       │   └── group_c/                   # Mayank — MS-1..MS-5

│       │       ├── architecture_01.schema.json

│       │       ├── compliance_01.schema.json

│       │       ├── success_metrics_01.schema.json

│       │       ├── open_questions_01.schema.json

│       │       └── next_steps_01.schema.json

│       │

│       ├── layout_registry.json           # BT-2 — allowed layoutIds only

│       ├── chapter_layout_map.json        # BT-3 — §13.2 default chapter → layout guidance

│       └── constraints/                   # BT-15, JJ-10, MS-12 — per-layout limits

│           ├── group_a.yaml

│           ├── group_b.yaml

│           └── group_c.yaml

│

├── scripts/

│   ├── generate_pydantic.py               # AT-4 — FrameworkObject, PresentationPlan, SlideSpecs

│   └── generate_typescript.py           # AT-5 — same schemas → renderer types

│

├── generated/

│   ├── python/                            # AT-4 output — do not hand-edit

│   │   └── contracts/

│   └── typescript/                        # AT-5 output — do not hand-edit

│       └── contracts/

│

├── apps/

│   ├── api/                               # AT-34 — FastAPI

│   │   ├── main.py

│   │   ├── config.py

│   │   ├── dependencies.py                # DI, auth, db session

│   │   ├── errors.py                      # Consistent error-response format

│   │   │

│   │   ├── routes/

│   │   │   ├── health.py

│   │   │   ├── opportunities.py           # AT-40 — §22.1

│   │   │   ├── transcripts.py             # AT-40 — upload, list, regenerate

│   │   │   ├── framework.py               # AT-41 — generate / regenerate_chapter / confirm / render

│   │   │   ├── presentation_plan.py       # AT-42 — plan from confirmed FrameworkObject

│   │   │   ├── presentation.py            # AT-43, AT-44 — generate, regenerate slide, change layout

│   │   │   └── jobs.py                    # AT-45 — stage, status, structured errors

│   │   │

│   │   ├── services/

│   │   │   ├── transcript/

│   │   │   │   ├── ingestion.py           # ES-1 — .txt/.vtt/.srt/.docx validate + normalize

│   │   │   │   ├── speaker_turns.py         # ES-2 — one entry per turn + speaker label

│   │   │   │   ├── conversation_ids.py    # ES-3 — stable ids across regeneration

│   │   │   │   └── pii_redaction.py       # ES-4 — strip PII before any LLM call (toggle per opp)

│   │   │   │

│   │   │   ├── knowledge_model/

│   │   │   │   ├── extraction.py          # ES-5 — Claude: transcript → KnowledgeModel

│   │   │   │   ├── source_refs.py         # ES-6 — conversation_id + turn pointer on every fact

│   │   │   │   ├── origin_classification.py  # ES-7 — SOURCE_FACT / USER_INPUT / AI_INFERENCE + confidence

│   │   │   │   └── contradictions.py      # ES-8 — structured conflict objects, never silent merge

│   │   │   │

│   │   │   ├── framework/

│   │   │   │   ├── synthesis.py           # ES-9 — Claude: KnowledgeModel → FrameworkObject (14 chapters)

│   │   │   │   ├── conflict_resolution.py # ES-10 — later source wins; else → open item

│   │   │   │   ├── quality_scores.py      # ES-11 — opportunity rating, conversation quality, build-readiness

│   │   │   │   ├── regenerate_chapter.py  # ES-12 — single chapter update + change log

│   │   │   │   ├── pre_confirm_check.py   # ES-13 — block ch.6 AI-used contradiction

│   │   │   │   │

│   │   │   │   └── chapter_validators/    # ES-14..ES-27 — acceptance spec per chapter

│   │   │   │       ├── ch00_about.py

│   │   │   │       ├── ch01_management_summary.py

│   │   │   │       ├── ch02_process_today.py

│   │   │   │       ├── ch03_aim_success.py

│   │   │   │       ├── ch04_solution_tobe.py

│   │   │   │       ├── ch05_how_it_works.py

│   │   │   │       ├── ch06_how_built.py

│   │   │   │       ├── ch07_client_needs.py

│   │   │   │       ├── ch08_security.py

│   │   │   │       ├── ch09_business_case.py

│   │   │   │       ├── ch10_complexity_timeline.py

│   │   │   │       ├── ch11_trustworthiness.py

│   │   │   │       ├── ch12_evolution_stages.py

│   │   │   │       └── ch13_next_steps_glossary.py

│   │   │   │

│   │   │   │   └── cross_chapter_rules.py # ES-28 no invented facts; ES-29 one opportunity per object

│   │   │   │

│   │   │   ├── presentation/

│   │   │   │   ├── planner.py             # BT-1 — OpenAI: FrameworkObject → PresentationPlan

│   │   │   │   └── layout_registry_guard.py  # BT-2 — reject unknown layoutId

│   │   │   │

│   │   │   ├── slides/

│   │   │   │   ├── content_generation/    # One OpenAI call per layout

│   │   │   │   │   ├── group_a/           # BT-9..BT-13

│   │   │   │   │   │   ├── cover_01.py

│   │   │   │   │   │   ├── context_01.py

│   │   │   │   │   │   ├── problem_solution_01.py

│   │   │   │   │   │   ├── scope_01.py

│   │   │   │   │   │   └── requirements_matrix_01.py

│   │   │   │   │   │

│   │   │   │   │   ├── group_b/           # JJ-5..JJ-8

│   │   │   │   │   │   ├── process_flow_01.py

│   │   │   │   │   │   ├── timeline_01.py

│   │   │   │   │   │   ├── milestones_01.py

│   │   │   │   │   │   └── team_fte_01.py

│   │   │   │   │   │

│   │   │   │   │   └── group_c/           # MS-6..MS-10

│   │   │   │   │       ├── architecture_01.py

│   │   │   │   │       ├── compliance_01.py

│   │   │   │   │       ├── success_metrics_01.py  # MS-14 — hard filter: no currency

│   │   │   │   │       ├── open_questions_01.py

│   │   │   │   │       └── next_steps_01.py

│   │   │   │   │

│   │   │   │   ├── source_chapter_enforcement.py  # BT-14, JJ-9, MS-11

│   │   │   │   └── business_rules/        # JJ-11..JJ-13, MS-13

│   │   │   │

│   │   │   ├── validation/

│   │   │   │   ├── constraint_validator.py    # AT-7 — generic required/type/count checks

│   │   │   │   ├── schema_validator.py        # AT-6 — schema_version + additive fields

│   │   │   │   ├── schema_retry.py            # ES-31, AT-15 — reject + retry on missing source_refs

│   │   │   │   └── compression_retry.py       # AT-8 — up to 2 AI-shortening passes

│   │   │   │

│   │   │   ├── jobs/

│   │   │   │   └── state_machine.py       # AT-36 — QUEUED → … → COMPLETED/FAILED (§24)

│   │   │   │

│   │   │   ├── audit/

│   │   │   │   └── audit_log.py           # AT-52 — actor + action + timestamp on state changes

│   │   │   │

│   │   │   └── observability/

│   │   │       └── llm_logger.py          # AT-53 — request id, stage, model, prompt version, tokens, latency

│   │   │

│   │   ├── llm/

│   │   │   ├── client.py                  # Provider abstraction

│   │   │   ├── claude/                    # ES-5, ES-9 — extraction + synthesis

│   │   │   │   └── prompts/

│   │   │   │       ├── extraction_v1.txt

│   │   │   │       └── synthesis_v1.txt   # ES-30 — layered blocks + chapter checklist

│   │   │   │

│   │   │   └── openai/                    # BT-1, slide content, AT-8 compression

│   │   │       └── prompts/

│   │   │           ├── presentation_planner_v1.txt

│   │   │           ├── slide_content/     # One prompt per layoutId

│   │   │           └── compression_v1.txt

│   │   │

│   │   └── db/                            # Supabase client / SQLAlchemy models mirroring §23

│   │       ├── models/

│   │       │   ├── opportunity.py

│   │       │   ├── transcript.py

│   │       │   ├── knowledge_model.py

│   │       │   ├── framework_object.py    # versioned; 14 chapters as JSONB

│   │       │   ├── presentation_plan.py

│   │       │   ├── slide_spec.py

│   │       │   ├── generation_job.py      # stage + status

│   │       │   ├── audit_log.py

│   │       │   └── llm_call_log.py

│   │       └── repositories/

│   │

│   ├── worker/                            # AT-35 — Celery + Redis

│   │   ├── celery_app.py

│   │   └── tasks/

│   │       ├── framework_extract.py       # ES-5 pipeline

│   │       ├── framework_synthesize.py    # ES-9 pipeline

│   │       ├── presentation_plan.py       # BT-1

│   │       ├── slide_generate.py          # BT/JJ/MS content calls

│   │       ├── slide_compress.py          # AT-8

│   │       └── deck_render.py             # dispatch → renderer service

│   │

│   ├── web/                               # AT-46..AT-49 — Next.js

│   │   └── src/

│   │       ├── app/

│   │       │   ├── upload/                # AT-46 — multi-file, client-side format reject

│   │       │   ├── framework-review/      # AT-47 — 14 chapters, source_refs, inline edit

│   │       │   ├── plan-preview/          # AT-48 — slide list before full generation

│   │       │   └── deck-center/           # AT-49 — per-slide PNG preview, pptx/pdf download

│   │       │

│   │       └── components/

│   │           ├── FrameworkChapterView.tsx

│   │           ├── SourceRefBadge.tsx

│   │           ├── PresentationPlanList.tsx

│   │           ├── SlidePreviewGrid.tsx

│   │           └── JobStatusTracker.tsx

│   │

│   └── renderer/                          # TypeScript — PPTX generation (AT-5 types)

│       ├── design_system/

│       │   ├── tokens/

│       │   │   ├── colors.ts              # AT-11 — no hardcoded hex in layouts

│       │   │   ├── typography.ts          # AT-12

│       │   │   └── spacing.ts             # AT-13

│       │   │

│       │   ├── masters/                   # AT-14..AT-18

│       │   │   ├── MASTER_DEFAULT.ts

│       │   │   ├── MASTER_COVER.ts

│       │   │   ├── MASTER_SECTION.ts

│       │   │   ├── MASTER_CONTENT.ts

│       │   │   └── MASTER_CLOSING.ts

│       │   │

│       │   └── components/                # AT-19..AT-32 — shared only, no per-layout styling

│       │       ├── addSlideTitle.ts

│       │       ├── addSectionLabel.ts

│       │       ├── addFooter.ts

│       │       ├── addContentCard.ts

│       │       ├── addKpiCard.ts

│       │       ├── addNumberBadge.ts

│       │       ├── addBulletList.ts

│       │       ├── addDataTable.ts

│       │       ├── addChart.ts

│       │       ├── addTimeline.ts

│       │       ├── addArchitectureNode.ts

│       │       ├── addConnector.ts

│       │       ├── addProcessStep.ts

│       │       └── addMilestone.ts

│       │

│       ├── layouts/

│       │   ├── group_a/                   # Blenard — BT-17..BT-21

│       │   │   ├── renderCover01.ts

│       │   │   ├── renderContext01.ts

│       │   │   ├── renderProblemSolution01.ts

│       │   │   ├── renderScope01.ts

│       │   │   └── renderRequirementsMatrix01.ts

│       │   │

│       │   ├── group_b/                   # Jaya — JJ-15..JJ-18

│       │   │   ├── renderProcessFlow01.ts

│       │   │   ├── renderTimeline01.ts

│       │   │   ├── renderMilestones01.ts

│       │   │   └── renderTeamFte01.ts

│       │   │

│       │   └── group_c/                   # Mayank — MS-16..MS-20

│       │       ├── renderArchitecture01.ts

│       │       ├── renderCompliance01.ts

│       │       ├── renderSuccessMetrics01.ts

│       │       ├── renderOpenQuestions01.ts

│       │       └── renderNextSteps01.ts

│       │

│       ├── dispatcher.ts                  # AT-33, BT-22, JJ-19, MS-21 — layoutId → render fn

│       │

│       ├── validation/                    # AT-9, AT-10

│       │   ├── libreoffice_pipeline.ts    # pptx → pdf + per-slide png

│       │   └── render_checks.ts           # slide count, blank slides, exceptions

│       │

│       └── server.ts                      # HTTP entry for worker deck_render task

│

├── supabase/

│   ├── migrations/                        # AT-37 — §23 tables, re-runnable

│   └── policies/                          # AT-38 — RLS; negative test required

│

├── config/

│   ├── tone_voice.yaml                    # ES-30 — loaded externally, never hardcoded

│   └── pii_redaction.yaml                 # ES-4 — per-opportunity toggle defaults

│

├── tests/

│   ├── unit/

│   │   ├── knowledge_model/               # ES-6, ES-7, ES-8

│   │   ├── framework/

│   │   │   ├── chapter_validators/        # ES-14..ES-27

│   │   │   ├── quality_scores.py          # ES-11

│   │   │   └── cross_chapter_rules.py     # ES-28, ES-29

│   │   ├── validation/                    # AT-7, AT-8

│   │   ├── slides/

│   │   │   ├── group_a/                   # BT-23

│   │   │   ├── group_b/                   # JJ-20, JJ-21

│   │   │   └── group_c/                   # MS-22

│   │   └── renderer/

│   │       └── dispatcher.test.ts

│   │

│   ├── integration/

│   │   ├── extraction_synthesis/          # ES-34 — ES-33 fixtures, all 14 chapters

│   │   └── full_pipeline/                 # AT-54 — upload → confirm → plan → slides → pptx

│   │

│   ├── eval/

│   │   ├── framework/                     # ES-35 — 10–20 transcripts + expected-behavior notes

│   │   └── fixtures/

│   │       └── transcripts/               # ES-33 — 2–3 hand-verified FrameworkObjects

│   │

│   └── golden_deck/                       # AT-55, BT-24, JJ-22, MS-23

│       ├── reference/                     # Approved PNG per layout (14 layouts)

│       ├── group_a/

│       ├── group_b/

│       ├── group_c/

│       └── run_regression.ts              # spacing / font / alignment / color diff

│

└── docs/

    ├── architecture.md                    # Pipeline diagram + domain boundaries

    ├── api.md                             # §22 endpoints; OpenAPI is source of truth

    ├── ticket_map.md                      # ES/AT/BT/JJ/MS ticket → folder mapping

    ├── framework_engine.md                # 2-pass: KnowledgeModel → FrameworkObject

    ├── presentation_pipeline.md           # Plan → SlideSpec → Render → Validate

    ├── design_system.md                   # Tokens, masters, component contract

    └── deployment.md                      # Docker Compose + Supabase setup
