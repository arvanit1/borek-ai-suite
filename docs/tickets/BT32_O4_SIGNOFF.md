# BT-32 O4 Production Sign-off

Technical evidence package for human O4 production approval of external-provider
egress.

Production classification was approved on 2026-09-11 by **O4 owner / Head of AI**.
No person name is recorded; the repository identifies the signer by role only.

Policy file (`config/data_egress_policy.yaml`) now records:

```yaml
approval:
  status: approved
  signed_off: true
  scheme: working_default
```

## Scope

What external-provider egress is being reviewed:

- Structured LLM planning / slide-generation / compression payloads sent to
  OpenAI or Anthropic after PII redaction.
- Named Gamma template slots (and, on deepening / concretisation, a fetchable
  client-logo HTTPS URL) sent to Gamma.
- Internal Gamma provider metadata (`themeId`, `gammaId`, `textMode`,
  `format`, `exportAs`).

What is **not** being approved:

- Sending raw Framework objects, `prior_stage_context`, or `grounded_facts`
  to Gamma.
- Sending Restricted fields under any profile.
- Sending any unlisted / unclassified field.
- Storing prompt bodies, transcripts, client values, or secrets in the audit
  trail.

## Providers

| Provider | Approved in policy | Runtime enforcement |
| --- | --- | --- |
| OpenAI | yes | `LlmClient` / `OpenAIResponsesExecutor` call `enforce_external_egress` before HTTP |
| Anthropic | yes | `llm.claude.client.structured_complete` filters `{system, user}` before HTTP |
| Gamma | yes | `generate_with_egress_policy` and `LiveGammaClient._filter_external_slots` filter the provider inventory before send |

An unknown provider receives an empty payload (`default: deny`).

## Classification model

| Class | Rule |
| --- | --- |
| Public | May leave if the provider is approved |
| Internal | May leave if the provider is approved |
| Client Confidential | May leave only if the provider **and** the exact/prefix path are allow-listed |
| Restricted | Never leaves. The working map has no Restricted entries; a Restricted extra classification is still denied |

Unclassified leaves are treated as deny.

## Default behavior

Default deny.

`requirements.unclassified_fields: deny`  
`requirements.restricted_fields: deny`  
`requirements.log_payload_values: false`

`EgressBlockedError.code == "EGRESS_BLOCKED"` is non-retryable. The provider
HTTP client is not invoked when any leaf is blocked.

## Stage coverage

JJ-31 frozen profiles in `packages/contracts/gamma_template.json`:

| Stage | Cards | Client logo | Pricing facts |
| --- | --- | --- | --- |
| `first_contact` | Cover, executive summary, context, problem/solution, next steps | no | no |
| `deepening` | Full 15-card set | yes | no |
| `concretisation` | Full 15-card set | yes | yes (facts stay in Borek retrieval; they are not a Gamma slot) |

Every named slot that those profiles can emit has a `/slots/...` classification
and, if client-confidential, a Gamma allow-list entry. `team.body` is
classified even though first contact does not emit it.

## Field inventory

No client values are shown. Paths use JSON Pointer notation. A path covers
itself and descendants unless a longer path overrides it.

### LLM planning / generation / compression (OpenAI, Anthropic)

| Path | Class | Providers | Decision | Source | Runtime |
| --- | --- | --- | --- | --- | --- |
| `/instructions` | internal | openai | allow | policy | `LlmClient._filter_external_request` |
| `/targetSchema` | internal | openai | allow | policy | same |
| `/layoutId` | internal | openai | allow | policy | same |
| `/chapterLayoutGuidance` | internal | openai | allow | policy | same |
| `/violations` | internal | openai | allow | policy | same |
| `/system` | internal | anthropic | allow | policy | `llm.claude.client` |
| `/frameworkObject` | client_confidential | openai | allow (allow-listed) | policy | planning payload |
| `/chapters` | client_confidential | openai | allow (allow-listed) | policy | slide generation |
| `/offendingValues` | client_confidential | openai | allow (allow-listed) | policy | compression |
| `/user` | client_confidential | anthropic | allow (allow-listed) | policy | framework synthesis |

### Gamma named slots (all three journey stages, subset per profile)

| Path | Class | Gamma allow-list | first_contact | deepening | concretisation |
| --- | --- | --- | --- | --- | --- |
| `/slots/cover.title` | internal | not required | yes | yes | yes |
| `/slots/cover.client_name` | client_confidential | yes | yes | yes | yes |
| `/slots/cover.subtitle` | client_confidential | yes | yes | yes | yes |
| `/slots/executive_summary.body` | client_confidential | yes | yes | yes | yes |
| `/slots/context.summary` | client_confidential | yes | yes | yes | yes |
| `/slots/problem_solution.body` | client_confidential | yes | yes | yes | yes |
| `/slots/next_steps.body` | client_confidential | yes | yes | yes | yes |
| `/slots/process_flow.body` | client_confidential | yes | no | yes | yes |
| `/slots/scope.in_scope` | client_confidential | yes | no | yes | yes |
| `/slots/requirements.body` | client_confidential | yes | no | yes | yes |
| `/slots/architecture.body` | client_confidential | yes | no | yes | yes |
| `/slots/compliance.body` | client_confidential | yes | no | yes | yes |
| `/slots/timeline.body` | client_confidential | yes | no | yes | yes |
| `/slots/milestones.body` | client_confidential | yes | no | yes | yes |
| `/slots/team.body` | client_confidential | yes | no | yes | yes |
| `/slots/success_metrics.body` | client_confidential | yes | no | yes | yes |
| `/slots/open_questions.body` | client_confidential | yes | no | yes | yes |

Source contract: `packages/contracts/gamma_template.json` plus
`config/data_egress_policy.yaml`. Runtime:
`services.gamma.provider_egress.gamma_content_egress_inventory` →
`generate_with_egress_policy` / `LiveGammaClient`.

### Gamma non-slot fields

| Path | Class | Decision | Notes |
| --- | --- | --- | --- |
| `/client_logo_url` | client_confidential | allow on Gamma only if fetchable owned HTTPS | first_contact does not emit; private/artifact/s3/foreign URLs never enter inventory |
| `/provider/themeId` | internal | allow | not customer content |
| `/provider/gammaId` | internal | allow | from-template id |
| `/provider/textMode` | internal | allow | scratch generation only |
| `/provider/format` | internal | allow | scratch generation only |
| `/provider/exportAs` | internal | allow | extra-format export |

### Explicitly not on the outbound Gamma request

| Object | Treatment |
| --- | --- |
| `prior_stage_context` | unclassified → deny; not in provider inventory |
| `grounded_facts` | unclassified → deny; not in provider inventory |
| raw Framework / chapter objects | not mapped onto Gamma slots |
| unknown nested fields | unclassified → deny |

## Negative controls

| Control | Proof |
| --- | --- |
| Unlisted field blocked, request not sent | `test_unclassified_field_fails_closed`, `test_live_llm_client_filters_before_executor`, `test_live_gamma_client_blocks_unclassified_before_http` |
| Restricted field blocked | `test_restricted_field_never_leaves`, `test_enforce_blocks_unclassified_and_restricted_leaves` |
| Raw `prior_stage_context` blocked | `test_raw_internal_objects_cannot_egress` |
| Raw `grounded_facts` blocked | same parametrized test |
| Contract drift blocked | `test_each_stage_profile_egress_surface_is_classified` plus in-memory mutation `test_contract_drift_new_template_slot_without_policy_fails_closed` |

## Audit evidence

Each `enforce_external_egress` decision writes a metadata-only row.

Durable table: `egress_audit` (`023_egress_audit.sql`). In-memory:
`EgressAuditRecord`. AT-52 companion action: `egress.allowed` / `egress.blocked`.

Recorded:

- opportunity
- presentation version
- journey stage
- provider
- pipeline stage
- decision (`allowed` / `blocked`)
- attempt
- field names
- classifications
- timestamp

Not recorded:

- prompt body
- transcript body
- client payload values
- API keys
- provider secrets
- full Framework payload

Allowed-send proof: `test_successful_send_writes_durable_metadata_only_audit`  
Blocked-send proof: `test_blocked_send_writes_durable_audit_without_values`  
Logo path audited without the URL: `test_deepening_owned_logo_send_audits_path_not_url`

## Live evidence

Reuse the already-landed AT-60B proof. **No new paid provider call was made
for this package.**

- Merge: PR #90 (`9edace3`), commit `b9fec57` — `BT: complete live Gamma integration`
- Adapter: `apps/api/services/gamma/live_client.py` applies BT-32
  `enforce_external_egress` on `gamma_live_egress_inventory` before HTTP
- That live first-contact run reached `POST /v1.0/generations/from-template`,
  completed generation, and filed artifacts (AT-60B / BT-28)
- The outbound inventory is named slots plus internal provider keys only.
  `prior_stage_context` and `grounded_facts` are not in
  `GAMMA_LIVE_HTTP_KEYS` and fail closed if introduced
- Durable metadata audit is the same `record_egress_decision` path used by
  the fixture and live clients

Automated E2E (`tests/integration/full_pipeline/test_bt30_e2e_gate.py`)
intentionally uses the Gamma fixture; it points at AT-60B for live evidence.

## Test evidence

Commands and counts from the preparing run on current main:

```
python -m pytest tests/unit/security/test_bt32_egress_classification.py -q
```

21 passed

```
python -m pytest tests/unit/security/test_egress_filter.py -q
```

6 passed

```
python -m pytest tests/unit/security/test_egress_policy_enforcement.py -q
```

11 passed

```
python -m pytest tests/unit/gamma/test_gamma_egress_policy.py tests/unit/gamma/test_at60_gamma_adapter.py tests/unit/gamma/test_at60_gamma_provider_contract.py tests/unit/gamma/test_jj31_stage_profiles.py -q
```

29 passed

Combined focused set: 67 passed.

`test_o4_approval_is_recorded` asserts `status: approved` and
`signed_off: true`. Approver identity stays in this document (role only);
the policy schema does not store a person name.

```
python scripts/validate_all.py
```

1832 passed, 2 skipped, 0 failed. `ALL CHECKS PASSED`.

```
git diff --check
```

PASS (no whitespace errors).

## Approval decision

O4 owner: O4 owner / Head of AI

Decision: APPROVED

Date: 2026-09-11

Evidence reviewed: BT-32 O4 production sign-off package

Comments: Production egress classification approved.

The repository identifies the signer by official role only. It does not name
a current person. Do not infer an approver from git history.
