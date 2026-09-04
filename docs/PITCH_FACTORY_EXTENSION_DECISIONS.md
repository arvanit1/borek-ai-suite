# Pitch Factory extension decisions

**Decision date:** 3 September 2026  
**Status:** approved working defaults for implementation  
**Scope:** client pack, Borek RAG, Gamma presentation channel, and filing

## Approved defaults

| Decision | Working default |
|---|---|
| O1 — formats | Information pack: PDF. Pitch: PPTX and PDF. Proposal: DOCX and PDF. In-app preview for all. |
| O2 — knowledge base | Enterprise document repository (SharePoint if that is Borek's standard) for files; Pitch Factory stores workflow, version, provenance, approval, and audit metadata. |
| O3 — rate cards | Versioned structured source owned by Commercial or Sales Ops. AI can explain an approved price but can never originate one. |
| O4 — confidential data | Public / Internal / Client Confidential / Restricted classification. External egress is fail-closed and controlled by provider and field allow-lists. |
| O5 — CI | Current CI is provisional v0.9. An approved machine-readable CI v1.0 is required before production. |
| O6 — approval | Sales approves normal collateral. Pricing/discount exceptions require commercial approval; legal exceptions escalate when relevant. |
| O7 — metrics | Speed, effort reduction, first-pass acceptance, commercial correctness, CI compliance, adoption, and traceability. |
| O8 — staffing | Continue with the current team. Add one experienced platform/fullstack engineer before real-source production integration if needed. |
| D1 — presentation engine | Gamma is the intended presentation engine. The internal renderer remains a feature-flagged fallback for one release. |
| D2 — templates | Start with one Borek pitch template. Add information-pack and proposal templates only after the pitch path is proven. |
| D3 — governance | Keep explicit human Framework approval before any presentation is generated. |
| D4 — branding source | Gamma template is the presentation CI source of truth. Internal design tokens remain for Framework PDF/DOCX and fallback rendering. |
| D5 — pricing | Generated prices are indicative and clearly labelled until Commercial approves offer-grade output. |

## Non-negotiable technical consequences

- No external provider receives an unclassified field.
- Restricted fields never leave Borek.
- Client Confidential fields require both an approved provider and an exact
  field allow-list entry.
- Every generated commercial number must carry a rate-card source and version.
- Missing company knowledge becomes an open question, never an AI guess.
- The Gamma path is not considered production-ready until a live API/template
  spike proves fidelity, limits, output ownership, failure behavior, and cost.
- Generated files are stored under Borek control even when an external provider
  creates them.

## Current external blocker

Working Gamma API credentials and a Borek template/template ID are not available
in the development environment. Fixture contracts and orchestration can be
built, but the live Gamma go/no-go remains blocked and must not be reported as
passed.

