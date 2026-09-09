# BT-29 — Progress mapping for the new stages

Phase 4. Owner: Blenard Tahiraj. Priority: P0.

BT-26 mapped the original backend stages to customer-facing names. The new
capability adds retrieval, Gamma, and filing. Those stages must follow the
same rules: real names, elapsed time, no invented percentages, no false timeout,
connection loss is not failure.

## What to deliver

Map every new backend stage to a customer-facing label, shown only when that
stage is actually running (same rule as today’s optional `GAMMA_RENDERING` /
`ARTIFACT_FILING` steps).

| Backend stage | Customer-facing name (working default) |
| --- | --- |
| Borek retrieval (AT-59 / ES-39, when it becomes a job stage) | Retrieving Borek information |
| `GAMMA_RENDERING` | Building your presentation |
| `ARTIFACT_FILING` | Archiving generated files |

Today `GAMMA_RENDERING` is labelled “Building branded presentation”. This ticket
aligns that copy with the team-plan wording and adds the retrieval step once
the backend reports it.

Rules carried forward from BT-26:

- Completed / current / upcoming plus elapsed time.
- No fake percentages.
- Running and failed never appear together.
- Connection loss never declares the job failed.
- Engine and vendor names stay out of the labels (JJ-28).

## Done when

A five-to-eight-minute job that includes retrieval and Gamma visibly progresses
through the new names. A job that never takes those stages never shows them.

## Proof

- Stage mapping unit tests for the new labels (no vendor names).
- Optional stages absent unless the backend reports them.
- Reconnect mid-Gamma or mid-retrieval resumes the same step.
- Failed Gamma/retrieval shows a failed step, not a timeout banner.

## Depends on

BT-26, AT-56 (durable reconnect), AT-60 / BT-28 (Gamma stage), AT-59 (retrieval
stage, when it exists).
