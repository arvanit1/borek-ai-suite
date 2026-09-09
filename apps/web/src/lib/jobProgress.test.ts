import assert from "node:assert/strict";

import {
  BOREK_RETRIEVAL_STAGE,
  EXTENSION_STAGE_LABELS,
  JOB_STAGE_LABELS,
  buildJobProgressView,
  elapsedMsSince,
  formatElapsed,
  formatElapsedLabel,
  jobProgressPhase,
  jobStageLabel,
  snapshotFromActiveJob,
  snapshotFromJob,
  type JobProgressSnapshot,
  type JobProgressStepState,
} from "./jobProgress.js";

const STARTED_AT = "2026-09-02T10:00:00.000Z";

function snapshot(overrides: Partial<JobProgressSnapshot> = {}): JobProgressSnapshot {
  return {
    jobId: "job-1",
    jobType: "presentation_generation",
    status: "RUNNING",
    currentStage: "SLIDE_GENERATING",
    startedAt: STARTED_AT,
    createdAt: STARTED_AT,
    completedAt: null,
    error: null,
    ...overrides,
  };
}

function states(view: ReturnType<typeof buildJobProgressView>): Record<string, JobProgressStepState> {
  assert.ok(view, "expected a progress view");
  return Object.fromEntries(view.steps.map((step) => [step.id, step.state]));
}

function labels(view: ReturnType<typeof buildJobProgressView>): string[] {
  assert.ok(view, "expected a progress view");
  return view.steps.map((step) => step.label);
}

// 1. Every real backend stage maps to the agreed customer-facing label.
{
  assert.equal(jobStageLabel("QUEUED"), "Waiting to start");
  assert.equal(jobStageLabel("TRANSCRIPT_PROCESSING"), "Processing customer context");
  assert.equal(jobStageLabel("KNOWLEDGE_EXTRACTING"), "Reading transcripts");
  assert.equal(jobStageLabel("FRAMEWORK_SYNTHESIZING"), "Building Framework");
  assert.equal(jobStageLabel("FRAMEWORK_VALIDATING"), "Checking Framework");
  assert.equal(jobStageLabel("PRESENTATION_PLANNING"), "Preparing presentation structure");
  assert.equal(jobStageLabel("SLIDE_GENERATING"), "Generating slide content");
  assert.equal(jobStageLabel("SLIDE_VALIDATING"), "Validating slides");
  assert.equal(jobStageLabel("PPTX_RENDERING"), "Rendering PowerPoint/PDF");
  assert.equal(jobStageLabel("GAMMA_RENDERING"), "Building your presentation");
  assert.notEqual(jobStageLabel("GAMMA_RENDERING"), "Building branded presentation");
  assert.equal(jobStageLabel("ARTIFACT_FILING"), "Archiving generated files");
  assert.equal(jobStageLabel("PREVIEW_RENDERING"), "Preparing preview");
  assert.equal(jobStageLabel(BOREK_RETRIEVAL_STAGE), "Retrieving Borek information");
  // No raw enum ever reaches the user, even for an unknown future stage.
  assert.equal(jobStageLabel("SOME_NEW_STAGE"), "Some new stage");
  assert.equal(jobStageLabel(null), "Waiting to start");
  for (const label of [...Object.values(JOB_STAGE_LABELS), ...Object.values(EXTENSION_STAGE_LABELS)]) {
    assert.doesNotMatch(label, /_/);
    assert.doesNotMatch(label, /%/);
    assert.doesNotMatch(label, /gamma|provider|template id/i);
  }
}

// 2. Presentation planning shows the real planning state.
{
  const view = buildJobProgressView({
    snapshot: snapshot({
      jobType: "presentation_planning",
      currentStage: "PRESENTATION_PLANNING",
    }),
  });
  assert.ok(view);
  assert.equal(view.phase, "planning");
  assert.equal(view.headline, "Preparing presentation structure");
  assert.deepEqual(states(view), {
    PRESENTATION_PLANNING: "current",
    SLIDE_GENERATING: "upcoming",
    SLIDE_VALIDATING: "upcoming",
    PREVIEW_RENDERING: "upcoming",
  });
  assert.deepEqual(labels(view), [
    "Preparing presentation structure",
    "Generating slide content",
    "Validating slides",
    "Preparing preview",
  ]);
}

// 3. Presentation generation walks the real generation stages.
{
  const expected: Array<[string, string]> = [
    ["SLIDE_GENERATING", "Generating slide content"],
    ["SLIDE_VALIDATING", "Validating slides"],
    ["PPTX_RENDERING", "Rendering PowerPoint/PDF"],
    ["GAMMA_RENDERING", "Building your presentation"],
    ["PREVIEW_RENDERING", "Preparing preview"],
  ];
  for (const [stage, headline] of expected) {
    const view = buildJobProgressView({ snapshot: snapshot({ currentStage: stage }) });
    assert.ok(view);
    assert.equal(view.phase, "generation");
    assert.equal(view.headline, headline);
    const stepStates = states(view);
    // Planning is finished by definition once a generation job exists.
    assert.equal(stepStates.PRESENTATION_PLANNING, "complete");
    assert.equal(stepStates[stage], "current");
  }

  const validating = buildJobProgressView({
    snapshot: snapshot({ currentStage: "SLIDE_VALIDATING" }),
  });
  assert.deepEqual(states(validating), {
    PRESENTATION_PLANNING: "complete",
    SLIDE_GENERATING: "complete",
    SLIDE_VALIDATING: "current",
    PREVIEW_RENDERING: "upcoming",
  });
}

// 4. Framework generation stages map to Framework copy, never presentation copy.
{
  const expected: Array<[string, string]> = [
    ["TRANSCRIPT_PROCESSING", "Processing customer context"],
    ["KNOWLEDGE_EXTRACTING", "Reading transcripts"],
    ["FRAMEWORK_SYNTHESIZING", "Building Framework"],
    ["FRAMEWORK_VALIDATING", "Checking Framework"],
  ];
  for (const [stage, headline] of expected) {
    const view = buildJobProgressView({
      snapshot: snapshot({ jobType: "framework_generation", currentStage: stage }),
    });
    assert.ok(view);
    assert.equal(view.phase, "framework");
    assert.equal(view.headline, headline);
    assert.equal(states(view)[stage], "current");
    assert.deepEqual(labels(view), expected.map(([, label]) => label));
  }
  assert.equal(jobProgressPhase("framework_generation"), "framework");
  assert.equal(jobProgressPhase("presentation_planning"), "planning");
  assert.equal(jobProgressPhase("presentation_generation"), "generation");
  assert.equal(jobProgressPhase("unknown_job"), null);
  assert.equal(buildJobProgressView({ snapshot: snapshot({ jobType: "unknown_job" }) }), null);
  assert.equal(buildJobProgressView({ snapshot: null }), null);
}

// 5. AT-56 reconnect: a recovered generation job resumes at its real stage.
{
  const recovered = snapshotFromActiveJob({
    job_id: "job-9",
    job_type: "presentation_generation",
    status: "RUNNING",
    current_stage: "PPTX_RENDERING",
    started_at: STARTED_AT,
    error: null,
  });
  const view = buildJobProgressView({ snapshot: recovered });
  assert.ok(view);
  assert.equal(view.headline, "Rendering PowerPoint/PDF");
  assert.notEqual(view.headline, "Preparing presentation structure");
  assert.deepEqual(states(view), {
    PRESENTATION_PLANNING: "complete",
    SLIDE_GENERATING: "complete",
    SLIDE_VALIDATING: "complete",
    PPTX_RENDERING: "current",
    PREVIEW_RENDERING: "upcoming",
  });
}

// 6. Planning → generation handoff is a neutral waiting state, not an error.
{
  const view = buildJobProgressView({
    snapshot: snapshot({
      jobType: "presentation_planning",
      status: "COMPLETED",
      currentStage: "COMPLETED",
      completedAt: "2026-09-02T10:01:00.000Z",
    }),
    handoff: true,
    plannedSlideCount: 12,
  });
  assert.ok(view);
  assert.equal(view.failed, false);
  assert.equal(view.error, null);
  assert.equal(view.headline, "Starting presentation generation");
  assert.equal(view.detail, "12 slides planned");
  assert.deepEqual(states(view), {
    PRESENTATION_PLANNING: "complete",
    SLIDE_GENERATING: "upcoming",
    SLIDE_VALIDATING: "upcoming",
    PREVIEW_RENDERING: "upcoming",
  });

  // Completed planning on its own never claims the generation stages are done.
  const planningOnly = buildJobProgressView({
    snapshot: snapshot({
      jobType: "presentation_planning",
      status: "COMPLETED",
      currentStage: "COMPLETED",
    }),
  });
  assert.ok(planningOnly);
  assert.equal(planningOnly.headline, "Presentation structure prepared");
  assert.equal(states(planningOnly).SLIDE_GENERATING, "upcoming");
}

// 7. A queued job says so instead of pretending work has started.
{
  const view = buildJobProgressView({
    snapshot: snapshot({ status: "QUEUED", currentStage: "QUEUED", startedAt: null }),
  });
  assert.ok(view);
  assert.equal(view.headline, "Waiting to start");
  assert.equal(view.elapsedFrom, STARTED_AT, "queued jobs fall back to created_at");
  assert.equal(states(view).SLIDE_GENERATING, "upcoming");
}

// 8. Backend failure stops progress at the failing stage with the real error.
{
  const view = buildJobProgressView({
    snapshot: snapshot({
      status: "FAILED",
      currentStage: "PPTX_RENDERING",
      error: {
        code: "RENDERER_FAILED",
        message: "The renderer could not produce the PowerPoint file.",
        stage: "PPTX_RENDERING",
        retryable: true,
      },
    }),
  });
  assert.ok(view);
  assert.equal(view.failed, true);
  assert.equal(view.headline, "The renderer could not produce the PowerPoint file.");
  assert.equal(view.error?.retryable, true);
  assert.deepEqual(states(view), {
    PRESENTATION_PLANNING: "complete",
    SLIDE_GENERATING: "complete",
    SLIDE_VALIDATING: "complete",
    PPTX_RENDERING: "failed",
    PREVIEW_RENDERING: "upcoming",
  });
}

// 9. Completion of a generation job is the presentation-ready state.
{
  const view = buildJobProgressView({
    snapshot: snapshot({
      status: "COMPLETED",
      currentStage: "COMPLETED",
      completedAt: "2026-09-02T10:04:00.000Z",
    }),
  });
  assert.ok(view);
  assert.equal(view.headline, "Presentation ready");
  assert.ok(view.steps.every((step) => step.state === "complete"));
  assert.equal(view.elapsedTo, "2026-09-02T10:04:00.000Z");
}

// 10. Slide-level Deck Center jobs keep their own scope.
{
  const view = buildJobProgressView({
    snapshot: snapshot({ jobType: "slide_regenerate", currentStage: "SLIDE_VALIDATING" }),
  });
  assert.ok(view);
  assert.equal(view.phase, "slide");
  assert.equal(view.title, "Updating the slide");
  assert.deepEqual(Object.keys(states(view)), [
    "SLIDE_GENERATING",
    "SLIDE_VALIDATING",
    "PREVIEW_RENDERING",
  ]);
}

// 11. Optional extension stages appear only when the backend reports them.
{
  const gamma = buildJobProgressView({
    snapshot: snapshot({ currentStage: "GAMMA_RENDERING" }),
  });
  assert.ok(gamma);
  assert.equal(gamma.headline, "Building your presentation");
  assert.equal(states(gamma).GAMMA_RENDERING, "current");
  assert.equal(states(gamma).PPTX_RENDERING, undefined);
  assert.equal(states(gamma).BOREK_RETRIEVAL, undefined);
  assert.equal(states(gamma).ARTIFACT_FILING, undefined);

  const filingFailure = buildJobProgressView({
    snapshot: snapshot({
      status: "FAILED",
      currentStage: "ARTIFACT_FILING",
      error: {
        code: "ARTIFACT_FILING_FAILED",
        message: "Generated files could not be archived.",
        stage: "ARTIFACT_FILING",
        retryable: true,
      },
    }),
  });
  assert.ok(filingFailure);
  assert.equal(states(filingFailure).ARTIFACT_FILING, "failed");
  assert.equal(states(filingFailure).GAMMA_RENDERING, undefined);
}

// 12. Slide counts are only shown when a real planned count exists.
{
  const withoutPlan = buildJobProgressView({ snapshot: snapshot() });
  assert.ok(withoutPlan);
  assert.equal(withoutPlan.detail, null);

  const singular = buildJobProgressView({ snapshot: snapshot(), plannedSlideCount: 1 });
  assert.equal(singular?.detail, "1 slide planned");

  const zero = buildJobProgressView({ snapshot: snapshot(), plannedSlideCount: 0 });
  assert.equal(zero?.detail, null);
}

// 13. Elapsed time comes from real timestamps and never predicts a finish time.
{
  const started = Date.parse(STARTED_AT);
  assert.equal(
    elapsedMsSince({ startedAt: STARTED_AT, createdAt: null, completedAt: null }, started + 18_000),
    18_000,
  );
  assert.equal(
    elapsedMsSince(
      { startedAt: null, createdAt: STARTED_AT, completedAt: null },
      started + 2_000,
    ),
    2_000,
    "queued jobs may fall back to created_at",
  );
  assert.equal(
    elapsedMsSince(
      { startedAt: STARTED_AT, createdAt: null, completedAt: "2026-09-02T10:00:42.000Z" },
      started + 600_000,
    ),
    42_000,
    "finished jobs freeze at their real completion timestamp",
  );
  assert.equal(
    elapsedMsSince({ startedAt: null, createdAt: null, completedAt: null }, started),
    null,
  );
  assert.equal(elapsedMsSince({ startedAt: "not-a-date", createdAt: null, completedAt: null }, started), null);
  assert.equal(formatElapsed(18_000), "18s");
  assert.equal(formatElapsed(102_000), "1m 42s");
  assert.equal(formatElapsed(3_930_000), "1h 5m");
  assert.equal(formatElapsedLabel(18_000), "Elapsed 18s");
  assert.doesNotMatch(formatElapsedLabel(18_000), /remaining|left|ETA|%/i);
}

// 13. Job snapshots read the real backend job payload.
{
  const mapped = snapshotFromJob({
    job_id: "job-77",
    job_type: "presentation_generation",
    status: "RUNNING",
    current_stage: "SLIDE_VALIDATING",
    created_at: STARTED_AT,
    started_at: STARTED_AT,
    completed_at: null,
    result: {},
    error: null,
    metrics: { total_tokens: 1234 },
  });
  assert.deepEqual(mapped, {
    jobId: "job-77",
    jobType: "presentation_generation",
    status: "RUNNING",
    currentStage: "SLIDE_VALIDATING",
    startedAt: STARTED_AT,
    createdAt: STARTED_AT,
    completedAt: null,
    error: null,
  });
  const view = buildJobProgressView({ snapshot: mapped });
  assert.ok(view);
  // Metrics are telemetry, not progress.
  assert.doesNotMatch(JSON.stringify(view), /1234|total_tokens/);
}

// 14. BT-29: retrieval is optional and uses the AT-59 contract name.
{
  const internal = buildJobProgressView({
    snapshot: snapshot({ currentStage: "SLIDE_VALIDATING" }),
  });
  assert.ok(internal);
  assert.equal(states(internal).BOREK_RETRIEVAL, undefined);
  assert.equal(states(internal).GAMMA_RENDERING, undefined);
  assert.doesNotMatch(labels(internal).join(" "), /Retrieving Borek|Building your presentation|Gamma/i);

  const retrieval = buildJobProgressView({
    snapshot: snapshot({ currentStage: BOREK_RETRIEVAL_STAGE }),
  });
  assert.ok(retrieval);
  assert.equal(retrieval.headline, "Retrieving Borek information");
  assert.deepEqual(states(retrieval), {
    PRESENTATION_PLANNING: "complete",
    SLIDE_GENERATING: "complete",
    SLIDE_VALIDATING: "complete",
    BOREK_RETRIEVAL: "current",
    PREVIEW_RENDERING: "upcoming",
  });
  assert.equal(states(retrieval).GAMMA_RENDERING, undefined);
  assert.doesNotMatch(JSON.stringify(retrieval.steps.map((step) => step.label)), /gamma|_/i);

  const bothReported = buildJobProgressView({
    snapshot: snapshot({
      status: "FAILED",
      currentStage: "GAMMA_RENDERING",
      error: {
        code: "GAMMA_TIMEOUT",
        message: "Gamma generation timed out.",
        stage: BOREK_RETRIEVAL_STAGE,
        retryable: true,
      },
    }),
  });
  assert.ok(bothReported);
  assert.deepEqual(Object.keys(states(bothReported)), [
    "PRESENTATION_PLANNING",
    "SLIDE_GENERATING",
    "SLIDE_VALIDATING",
    "BOREK_RETRIEVAL",
    "GAMMA_RENDERING",
    "PREVIEW_RENDERING",
  ]);
  assert.equal(states(bothReported).BOREK_RETRIEVAL, "failed");
  assert.equal(states(bothReported).GAMMA_RENDERING, "upcoming");
  assert.doesNotMatch(bothReported.headline, /gamma/i);
  assert.doesNotMatch(bothReported.headline, /timeout banner|%/i);

  const retrievalFailure = buildJobProgressView({
    snapshot: snapshot({
      status: "FAILED",
      currentStage: "FAILED",
      error: {
        code: "KNOWLEDGE_READ_FAILED",
        message: "Borek information could not be retrieved.",
        stage: BOREK_RETRIEVAL_STAGE,
        retryable: true,
      },
    }),
  });
  assert.ok(retrievalFailure);
  assert.equal(retrievalFailure.failed, true);
  assert.equal(states(retrievalFailure).BOREK_RETRIEVAL, "failed");
  assert.equal(retrievalFailure.headline, "Borek information could not be retrieved.");
  assert.equal(states(retrievalFailure).GAMMA_RENDERING, undefined);

  const gammaFailure = buildJobProgressView({
    snapshot: snapshot({
      status: "FAILED",
      currentStage: "FAILED",
      error: {
        code: "GAMMA_TIMEOUT",
        message: "Gamma generation timed out.",
        stage: "GAMMA_RENDERING",
        retryable: true,
      },
    }),
  });
  assert.ok(gammaFailure);
  assert.equal(states(gammaFailure).GAMMA_RENDERING, "failed");
  assert.equal(states(gammaFailure).BOREK_RETRIEVAL, undefined);
  assert.doesNotMatch(gammaFailure.headline, /gamma/i);
  assert.equal(
    gammaFailure.headline,
    "Building the branded presentation took too long. Try generating it again.",
  );

  const reconnected = buildJobProgressView({
    snapshot: snapshotFromActiveJob({
      job_id: "job-reconnect",
      job_type: "presentation_generation",
      status: "RUNNING",
      current_stage: BOREK_RETRIEVAL_STAGE,
      started_at: STARTED_AT,
      error: null,
    }),
  });
  assert.ok(reconnected);
  assert.equal(reconnected.headline, "Retrieving Borek information");
  assert.equal(states(reconnected).BOREK_RETRIEVAL, "current");
  assert.equal(states(reconnected).GAMMA_RENDERING, undefined);
  assert.equal(reconnected.failed, false);
}

console.log("jobProgress tests passed");
