# BT-32 — Egress classification and allow-list, production closure

Phase 4. Owner: Blenard Tahiraj. Priority: P0.

Jaya does not co-own this. JJ-31 hands over one thing — the slot list per stage
profile — and that list is frozen in the contract before classification starts,
so this ticket does not wait on her implementation.

This is the O4 work that has never had a ticket number. The pieces exist:
`config/data_egress_policy.yaml` classifies fields, the filter code refuses
unlisted ones, and JJ-26 already requires every chapter-fed slot to be
allow-listed. What does not exist is closure — nobody has signed off that the
classification matches what Borek permits to leave, the new JJ-31 stage
profiles are not covered, and there is no record of what actually left.

Unnumbered security work does not get finished. This ticket numbers it.

## What to deliver

- Every field that can reach an external provider classified under the O4
  scheme: Public, Internal, Client Confidential, Restricted.
- Coverage for all three JJ-31 stage profiles, not just the original single
  slot set. Restricted never leaves under any profile.
- Fail-closed by default: an unlisted field is `EGRESS_BLOCKED`, and adding a
  slot to the contract without a policy entry fails in CI rather than in
  production.
- An audit record per outbound send: opportunity, version, stage, provider,
  the field names and their classifications, and the decision. The payload
  itself is not stored; the point is answering "what client data went out for
  this version", not duplicating the data.
- Written sign-off from whoever owns O4 that the classification is correct,
  referenced from the policy file.

## Done when

No field leaves Borek without an explicit classification and an allow-list
entry for that provider and that stage. A newly added slot with no policy entry
fails closed in test and live. The audit trail answers what client data was
sent for any given version.

## Proof

- Policy coverage test across all three stage profiles.
- Negative test: unlisted field → `EGRESS_BLOCKED`, request not sent.
- Negative test: Restricted field never egresses, under any profile.
- Audit row present for each send, with no payload body stored (AT-52 log).
- Contract drift test: slot added to `gamma_template.json` without a policy
  entry fails CI.
- O4 sign-off recorded, not assumed.

## Depends on

JJ-26 (slot allow-list requirement), JJ-31 for the frozen slot list only,
AT-60 (live provider contract — same owner), AT-52 (audit log), O4 decision
and sign-off.
