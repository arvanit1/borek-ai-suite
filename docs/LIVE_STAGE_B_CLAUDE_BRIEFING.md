# Live Stage B briefing — send this whole file to Claude

Use this as the system/user context for fixing live **Generate deck**. Do not invent tickets. Do not edit another owner’s files unless the human explicitly assigns that work.

---

## 1. Who, product, and goal

- Product: **Borek AI Suite** — transcript → Framework (Stage A, Claude) → confirmed review → Presentation plan + SlideSpecs (Stage B, OpenAI) → PPTX/PDF (deterministic renderer).
- Repo: `borek-ai-suite`. Live work is on branch **`blenard`** (uncommitted live Stage B + store/extraction hardening).
- Human: **Arvanit (AT)** — platform/spine. He authorized completing **live** Stage B on this branch so a real opportunity can produce a real deck.
- **Goal right now:** live `POST .../presentation/generate` succeeds for opportunity `aff77ed5-274a-4c15-88c4-d55460df3a1a` (framework + plan already exist). Fixture E2E already works.

**Do not commit unless asked. Do not print `.env` secrets.**

---

## 2. Ownership (do not cross unless assigned)

| Owner | Tickets | Touch these | Do not “finish” their tickets by editing their contracts |
|---|---|---|---|
| Arvanit AT-1..55 | Platform, AT-7/AT-8 validation, compose, web, store | `apps/services/api`, `apps/api/llm` live adapter, AT-7/8 **behavior** only if required | — |
| Endrit ES-* | Transcript, KnowledgeModel, 14-chapter synthesis | `apps/api/services/knowledge_model`, `framework/` | Don’t change FrameworkObject schema |
| **Blenard BT-*** | Group A: COVER, CONTEXT, PROBLEM_SOLUTION, SCOPE, REQUIREMENTS_MATRIX | `group_a/` generate + render, BT-14 path | — |
| Jaya JJ-* | Group B: PROCESS_FLOW, TIMELINE, MILESTONES, TEAM_FTE | Prefer **live adapter** only | **Do not edit** `packages/contracts/slide_spec/group_b/*` or `group_b/` generators unless assigned |
| Mayank MS-* | Group C | Same as JJ | **Do not edit** `group_c/` schemas/generators unless assigned |

`EXECUTIVE_SUMMARY_01` has **no owner**. Registry lists it; no generator; renderer is a stub. Live code **skips** it. Do not implement that layout unless assigned.

Canonical ticket text: `.tmp_extract/Development_Task_Backlog_Detailed.txt`  
Stage A/B spec: `.tmp_extract/Framework_and_Presentation_Pipeline_Full_Technical_Plan_v2.txt` (§9–15, §18)  
Scope: `docs/SCOPE.md`

---

## 3. Latest failure (the one to explain / fix next)

```
CONTEXT_01 contains numeric content at problem.description
absent from its field-attributed chapters: 3
```

This is **`UngroundedContentError`** (BT-14 numeric grounding), **not** schema, not compression.

### What the rule is

In `apps/api/services/slides/content_generation/group_a/common.py`:

- Every populated content leaf must have `fieldProvenance[].sourceChapterIds`.
- Any **number token** in that leaf’s text must appear in the **attributed chapter bodies**, not merely in the Framework, and not in a different chapter.
- Token regex: `(?<![\w])\d+(?:[.,]\d+)?%?(?![\w])` then `%` stripped and `,` → `.`
- So the digit **`3`** (or `3,000` → `3.000`, or `3%` → `3`) is in `problem.description`, and **none** of the chapters listed on `fieldProvenance` for `problem.description` contain that token.

`CONTEXT_01` is only allowed to read **chapters `1` and `2`** (BT-10). Chapter `3` of the Framework is **not** in the generate request. If the model writes “3-way”, “3 minutes”, “3,000 invoices”, or “stage 3”, that `3` must occur in chapter 1 and/or 2 **and** those ids must be on that field’s provenance.

Official fixture pattern (`packages/contracts/fixtures/slide_spec/group_a/context_01.minimal.json`):

- `title` → `["1","2"]` (slide-level, both request chapters)
- `problem.description` → `["2"]` only — so a number that exists only in chapter 1 **must not** be attributed to chapter 2.

Unit test that defines the ticket: `test_bt14_numeric_grounding_uses_the_fields_attributed_chapters` in `tests/unit/slides/test_group_a_content_generation.py` (`80%` fails on chapter 2, passes when provenance is `["1"]`).

### Likely live causes (check logs / last SlideSpec, do not guess in code)

1. OpenAI attributed `problem.description` to `["2"]` but the sentence uses a `3` that only appears in chapter 1 (or only in chapter 3+, which was never sent).
2. Live repair stamped a **missing** required leaf with **all request chapters** `["1","2"]` — then `3` is still missing from **both** chapter 1 and 2 bodies (model invented it, or it came from “3-way match” / opportunity name not in those chapter bodies).
3. Compression / word-trim kept a number while provenance stayed on the wrong chapter.

**BT-14 forbids** accepting the field with no source, and **forbids** inventing a chapter. Legal fixes:

- Ask the model (retry) to drop or rephrase the number, **or** retarget provenance to a request chapter that actually contains the token.
- Do **not** add chapter `"3"` to CONTEXT (BT-10: chapters 1–2 only).
- Do **not** strip all numbers as a silent hack if they are grounded.
- Do **not** disable `_validate_numeric_grounding`.

---

## 4. Why “tickets are implemented” and live still fails

Fixture path uses hand-written SlideSpecs that already satisfy BT-14/15/16. Live OpenAI does not.

| Layer | Ticket intent | Live gap we keep hitting |
|---|---|---|
| OpenAI `json_schema` | Bound to layout schema | `strict: false` — `maxLength` / `maxItems` / extra keys are hints |
| BT-14 | Every leaf traced; numbers only from attributed chapters | Model omits provenance; or attributes the wrong chapter; or invents a digit |
| BT-15 / AT-8 | Limits + up to 2 shorten passes; **never mid-word silent truncate** | Compressor used to get a schema with no `maxLength`; AT-8 then correctly `VALIDATION_FAILED` |
| JJ schemas | `additionalProperties: false`, **no** `fieldProvenance` property | Flattened OpenAI schema inherits base `fieldProvenance` → Group B jsonschema reject |
| Plan | `EXECUTIVE_SUMMARY_01` in registry + chapter map | No generator — skip only |

Fail-closed validators are **correct**. Live adapter must make OpenAI output **legal** without weakening tickets.

---

## 5. Stage B generate-deck requirements (this click)

After confirmed Framework + saved PresentationPlan:

1. **BT-1 / BT-2 / BT-3** — plan already done on this opportunity.
2. **Per planned slide** — owner generator → valid SlideSpec from **allowed chapters only** (BT-9…13, JJ-5…8, MS).
3. **BT-14 / JJ-9 / MS-11** — Group A: full `fieldProvenance`. Group B today: **root** `sourceChapterIds` only (schema rejects `fieldProvenance`). Group C: field provenance like Group A.
4. **BT-15 + JJ/MS limits** via AT-7 (`packages/contracts/constraints/*.yaml`). CONTEXT `problem.description` **max 160**.
5. **BT-16 + AT-8** — only `max_length` is compressible; extra array items fail closed (never silently delete in AT-8). Live clamp of `max_items` exists in repair (first N) because OpenAI ignores `maxItems`.
6. **§15.1** — 2 AI shorten attempts; still failing → `VALIDATION_FAILED` (spec: flag slide; **current platform raises and kills the whole deck job**).
7. **§13.2 / Group A** — no commercial/currency on slides; no new facts.
8. Render — BT-17…22 / JJ / MS / AT-33. No LLM.

CONTEXT specifically:

- BT-5: four blocks `problem` / `solution` / `currentState` / `targetState` (`title` + `description`).
- BT-10: chapters **1 and 2 only**.
- BT-18: renderer already exists.

---

## 6. What we already changed on `blenard` (uncommitted / docker-cp’d)

Do not revert these without reason. Images bake code; after file edits: `docker cp` into `borek-ai-suite-api-1` and `borek-ai-suite-worker-1` then `docker compose restart api worker`.

| Change | Files | Why |
|---|---|---|
| Live OpenAI SlideSpec + flatten `allOf`/`$ref`; stamp BT-15 limits on **request** schema | `apps/api/llm/openai_executor.py`, `json_schema_bundle.py`, `client.py` | Cover schema was illegal at OpenAI root (`allOf`/`const`) |
| Live factories, no fixture fallback in live | `stage_b_providers.py`, `stage_b_orchestration.py` | Fail closed if live provider missing |
| Extraction `max_tokens` 64k + truncation retry | `apps/api/llm/claude/client.py`, `extraction.py` | ES-5 KnowledgeModel was cut at 12k |
| Supabase pool + retry; audit must not fail 202 | `supabase_store.py`, `audit_log.py` | UI “Failed to fetch” |
| Skip `EXECUTIVE_SUMMARY_01` | `generatable_layouts.py`, planner target schema, store generate loop | No owner generator |
| Group A live provenance | `live_slide_repair.py` | 1 chapter: fill all missing; multi-chapter optional: drop; **required** missing: stamp **all request chapter ids** (CONTEXT fixture `title`) |
| Compression `maxLength` + word-boundary fit | `apps/api/llm/client.py` `compression_fields_fn` | AT-8 was failing because compressor schema was `{type:string}` only |
| Strip undeclared keys / `fieldProvenance` when layout schema does not list it | `live_slide_repair.py` | PROCESS_FLOW `additionalProperties: false` |

**Still not applied unless stashed:** AT store fix that stops download overwriting live PPTX with the fixture deck.

**UI:** `waitForJob` is **240s**. Live Stage A (Claude) can take ~6 minutes. Worker can succeed after the page times out.

---

## 7. Files to read first for *this* error

```
apps/api/services/slides/content_generation/group_a/context_01.py
apps/api/services/slides/content_generation/group_a/common.py   # _validate_numeric_grounding
apps/api/llm/live_slide_repair.py
apps/api/llm/client.py                                         # structured_generator + compression
apps/services/api/app/services/stage_b_orchestration.py
apps/services/api/app/services/stage_b_providers.py
packages/contracts/slide_spec/group_a/context_01.schema.json
packages/contracts/constraints/group_a.yaml                    # CONTEXT 160
packages/contracts/fixtures/slide_spec/group_a/context_01.minimal.json
tests/unit/slides/test_group_a_content_generation.py
tests/unit/api/test_live_slide_repair.py
.tmp_extract/Development_Task_Backlog_Detailed.txt             # BT-10, BT-14, BT-15, BT-16, AT-8
```

Live generate request only includes `config.allowed_chapter_ids` chapter bodies (commercial-sanitized). CONTEXT = 1, 2.

---

## 8. Errors already seen on this opportunity (do not regress)

1. No live structured provider → registered.
2. OpenAI 400 invalid schema (`allOf` at root) → flatten request schema only.
3. `statBadges` 4 or 5 > 3 → clamp first N in repair (AT-8 will not delete extras).
4. Missing `fieldProvenance` for `sectionLabel` / `title` → Group A repair rules above.
5. `UNSUPPORTED_SLIDE_GENERATOR: EXECUTIVE_SUMMARY_01` → skip unimplemented.
6. `CONTEXT_01` `problem.description` 192 > 160 after 2 compressions → bind `maxLength` + word-safe fit in live compressor.
7. `PROCESS_FLOW_01` extra `fieldProvenance` → strip if schema properties omit it.
8. **Now:** ungrounded `3` on `problem.description`.

---

## 9. Constraints for any fix

- Keep BT-14: no number unless it appears in **that field’s** attributed chapter text.
- Keep BT-10: CONTEXT never cites chapters other than 1 and 2.
- Keep AT-8: no mid-word silent truncate as the **success** path for overflow; 2 AI passes then `VALIDATION_FAILED` is still legal.
- Do not edit JJ/MS/ES schemas or generators unless the human says so. Live adapter (`apps/api/llm/*`, `stage_b_*`) is the preferred place.
- Do not put fixture fallbacks back into live `stage_b_orchestration.py`.
- Prefer retry / rewrite / correct provenance over dropping the slide or weakening the validator.

---

## 10. How to verify

```text
py -m pytest tests/unit/slides/test_group_a_content_generation.py tests/unit/api/test_live_slide_repair.py tests/unit/api/test_bt_live_slide_generation.py -q
```

Then `docker cp` changed files into api + worker, `docker compose restart api worker`, click **Generate deck** again.

Watch: `docker compose logs worker --since 5m`

Success signals: OpenAI 200 per slide, renderer `/render` 200, Celery `run_presentation_generation` succeeded.

---

## 11. Ask Claude to do

1. Explain this `3` error in terms of BT-14 (which chapter token set vs which provenance).
2. Propose a **live-adapter** fix that stays ticket-legal (retry with “remove or re-attribute numbers”; or if the token exists in another **allowed** request chapter, expand that field’s `sourceChapterIds` to include it — never invent chapter 3).
3. Add a unit test that would have caught this case.
4. List files you will change before editing.
5. Do not implement EXECUTIVE_SUMMARY_01, ES synthesis, or JJ/MS schema additions unless asked.
