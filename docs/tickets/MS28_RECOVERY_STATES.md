# MS-28 — Recovery states for the new stages

Phase 4. Owner: Mayank Somwani. Priority: P1.

MS-25 classified failures as CONNECTION_LOST, STILL_RUNNING, RETRYING,
INPUT_REQUIRED, VALIDATION_NEEDS_REVIEW or TERMINAL_FAILURE. The new stages
introduce retrieval misses, Gamma failures, credential problems, and a
missing or changed template. Those must map into the same categories with a
correct next action — and must never name the vendor.

## What to deliver

Extend `recoveryUx` (and the single dominant banner) for:

| Situation | Category | Next action |
| --- | --- | --- |
| Retrieval returned nothing for a required commercial fact | INPUT_REQUIRED or still-running open-question, never a crash | Review Framework / continue without invented prices |
| Gamma timeout or rate limit | RETRYING or retryable TERMINAL_FAILURE | Try generating again |
| Credentials rejected / template missing or locked | TERMINAL_FAILURE (admin setup) | Ask an administrator to check the setup |
| Payload rejected (content) | VALIDATION_NEEDS_REVIEW | Review the Framework, then retry |
| Engine flag off after a Gamma failure | STILL_RUNNING / success on fallback | Ready screen still works (JJ-28) |

JJ-28 already maps `GAMMA_*` codes to engine-neutral copy on the progress and
ready screens. This ticket owns *recovery*: the category, the one banner, and
the button. Do not print stack traces. Technical identifiers stay behind
Details.

## Done when

A normal user who hits retrieval failure, Gamma failure, a credential problem,
or a missing template sees an understandable state and the correct next action.
No banner names Gamma. Only one dominant banner at a time.

## Proof

- Fixture per situation above (extend `recoveryUx.test.ts` / MS-25 tests).
- Gamma auth / template-locked never offer a pointless retry if AT-57 marks
  them non-retryable.
- Retrieval miss does not look like a crashed job.
- Reconnect during Gamma is STILL_RUNNING, not CONNECTION_LOST failure.

## Depends on

MS-25, AT-57 (retryability), AT-60, BT-28, JJ-28 (engine-neutral messages).
