# Phase 2 technical spikes — RAG and Gamma

**Date:** 3 September 2026  
**Owner:** Arvanit (AT)  
**Scope:** bounded spikes only. Not AT-59 or AT-60 production delivery. Not wired into the job pipeline, worker, or migrations.

## Verdict

| Spike | Local contract | Live go / no-go |
|---|---|---|
| RAG (dummy versioned corpus) | **GO for the retrieval contract** | Production corpus location, rate-card owner, and update cycle remain **BLOCKED on O2/O3** |
| Gamma | **GO for the adapter contract + fixture behaviour** | **NO live go.** Live API fidelity, authentication, template mechanics, rate limits, and cost remain **BLOCKED pending Gamma access** |

Do not treat the fixture client as evidence that Gamma will accept this payload in production.

## RAG spike

**What was proved**

- Dummy Borek corpus `borek-internal-dummy` version `2026.09.01` includes at least one **pricing** fact (Senior Consultant day rate EUR 1250.00, indicative) and one **staffing** fact (Invoice 3-way Match core team 4 people / 2.6 FTE).
- Answers return traceable metadata: `corpus_id`, `corpus_version`, `document_id`, `document_type`, `document_version`, `fact_id`, validity window, and classification.
- Unsupported or vague questions return `status=unknown` with no statement, payload, or sources. The retriever does not interpolate or invent rates.

**What this is not**

- Not embeddings, not a vector store, not offer-grade pricing.
- Not AT-59 ingestion, retrieval API, or RLS.
- Dummy amounts must not appear in client-facing documents.

**Code**

- `apps/api/services/borek_rag/`
- `apps/api/services/borek_rag/data/borek_corpus_v1.json`
- `tests/unit/rag/test_borek_rag_spike.py`

## Gamma spike

**Constraint:** there is no live Gamma credential or template access in this environment.

**What was proved (fixture only)**

- Provider protocol `GammaProvider.generate(GammaGenerateRequest) -> GammaGenerateResult`.
- Payload shape: named content slots only (`cover.title`, …). Layout/styling keys are rejected.
- Template locking: only `borek-branded-standard` / `v1`; branding slots such as `brand_color` are rejected as template-locked.
- Optional client logo as an owned storage reference (`artifact:logos/…` or `s3://borek-client-logos/…`), not an arbitrary URL.
- Artifact metadata for PPTX and PDF: content type, byte size, SHA-256, storage key.
- Artifact ownership: `owner_opportunity_id`, `owner_presentation_version_id`, and storage key prefix `gamma/{opportunity}/{presentation_version}/`.
- Error classification: `timeout`, `auth`, `template`, `payload`, `rate_limit`, `provider`, with retryable flags.

**BLOCKED — do not claim live go**

| Unknown | Status |
|---|---|
| Live authentication / token lifetime | BLOCKED |
| Real Borek template id and slot names in Gamma | BLOCKED (JJ-26) |
| Whether Gamma accepts a per-generation client logo | BLOCKED |
| Live request/response fidelity vs this contract | BLOCKED |
| Rate limits | BLOCKED |
| Latency and timeouts under load | BLOCKED |
| Cost per generation | BLOCKED |
| PPTX/PDF binary identity vs Gamma export | BLOCKED |

A written Gamma confirmation (D1) and credentials are required before AT-60.

**Borek theme (built 2026-09-03, workspace `Arvanit Telaku's Workspace`)**

A Gamma theme was created by importing `AI-Support-Agent 3.pptx` and then corrected by hand.
This covers branding (colours, fonts, logo) only; it is *not* a template and does not unblock
the slot/layout unknowns above.

| Property | Value |
|---|---|
| Theme name | `Borek Pitch Theme` |
| `themeId` (for API `POST /v1.0/generations`) | `4kv51cbpy4xonmj` |
| Workspace default | yes |
| Primary accent | `#2C567A` (PPTX `accent1`) |
| Secondary accents | `#3B76A6`, `#44546A`, `#0072C7` |
| Heading colour | `#0D1D51` (PPTX `accent3`) |
| Background | `#FFFFFF` |
| Heading / body font | Inter / Inter |

Corrections applied to Gamma's PPTX import, which guessed several values wrongly:

- Heading font came in as **Alice**, a serif Gamma picked up from an East-Asian fallback tag in
  the slide XML, and its Bold weight raised a warning. The PPTX font scheme actually specifies
  **Everett** for *both* major and minor fonts. Everett is absent from Gamma's library and
  custom font upload is Pro-only, so both roles are set to Inter as the closest neo-grotesque.
- Gamma invented a tint `#7FB4DB` that is not in the Borek palette, while the real brand blue
  `#0072C7` (PPTX `accent2`) was dropped. Replaced the former with the latter.

**Visual theme test (2026-09-03)**

Generated `https://gamma.app/docs/Borek-Pitch-Theme-Test-k7se1gl0bnia8uy` with
`Borek Pitch Theme` as workspace default. Measured on the cover:

- Heading colour `rgb(13, 29, 81)` = `#0D1D51`
- Heading font Inter 700
- Accent numbers / pills use the `#2C567A` family
- Theme logo is `Logo-dark.svg`. A Gamma theme logo sits in the *editor chrome*
  by default and is **not** stamped onto generated slides. It was added to
  All slides → Headers & footers → bottom-left after generation. This is a
  per-deck Page setup step, not automatic branding from `themeId`.

This is a UI theme check only. Live `POST /v1.0/generations` is still blocked (no API key).

**Outstanding on the theme**

- The white wordmark belongs in the *inverted logo* slot so it swaps in on dark backgrounds,
  but that slot is Pro-only on this workspace.
- Body colour is Gamma's default `#2C2821`, a warm near-black that sits slightly off a palette
  that is otherwise cool. Cosmetic; a CI decision rather than a defect.
- API key generation is not available on this Free workspace, so `themeId` above is recorded
  for later use but remains unexercised against the live API.

**Code**

- `apps/api/services/gamma/contract.py`
- `apps/api/services/gamma/fixture_client.py`
- `tests/unit/gamma/test_gamma_spike.py`

## Explicit non-goals (this spike)

- No job stage, feature flag, Celery task, or worker change.
- No database migration.
- No calls to Gamma or any external model.
- No outbound classification allow-list (O4) — still a later AT item.
