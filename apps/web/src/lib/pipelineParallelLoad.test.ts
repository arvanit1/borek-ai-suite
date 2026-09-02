import assert from "node:assert/strict";

import { buildJobProgressView, type JobProgressSnapshot } from "./jobProgress.js";
import {
  PIPELINE_JOB_POLL_MS,
  startPipelineParallelLoad,
  type PipelineParallelLoadHandlers,
} from "./pipelineParallelLoad.js";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function createHarness() {
  let contentLoaded = false;
  let contentLoading = true;
  let jobPolling = false;
  const events: string[] = [];
  const snapshots: JobProgressSnapshot[] = [];
  const jobFailures: unknown[] = [];

  const handlers: PipelineParallelLoadHandlers = {
    onContentLoaded: () => {
      contentLoaded = true;
      events.push("content_loaded");
    },
    onContentMissing: () => {
      contentLoaded = false;
      events.push("content_missing");
    },
    onContentLoadFinished: () => {
      contentLoading = false;
      events.push("content_load_finished");
    },
    onContentLoadError: () => {
      contentLoading = false;
      events.push("content_load_error");
    },
    onJobPollingStart: () => {
      jobPolling = true;
      events.push("job_polling_start");
    },
    onJobStageUpdate: () => {
      events.push("job_stage_update");
    },
    onJobSnapshot: (snapshot) => {
      snapshots.push(snapshot);
    },
    onJobPollingFinished: () => {
      jobPolling = false;
      events.push("job_polling_finished");
    },
    onJobFailed: (error) => {
      jobFailures.push(error);
      events.push("job_failed");
    },
  };

  return {
    handlers,
    contentVisible: () => contentLoaded && !contentLoading,
    jobIndicatorVisible: () => jobPolling,
    events,
    snapshots,
    jobFailures,
  };
}

async function testPlanLoadsIndependentlyOfJobPolling(): Promise<void> {
  const harness = createHarness();
  let jobPollCount = 0;

  const cancel = startPipelineParallelLoad(
    "plan",
    harness.handlers,
    {
      loadContent: async () => {
        await delay(100);
      },
      isMissingError: () => false,
      getActiveJob: async () => {
        await delay(500);
        return {
          job_id: "job-1",
          job_type: "presentation_planning",
          status: "RUNNING",
          current_stage: "PRESENTATION_PLANNING",
          started_at: "2026-09-01T12:00:00Z",
          error: null,
        };
      },
      getJob: async () => {
        jobPollCount += 1;
        await delay(100);
        return {
          job_id: "job-1",
          job_type: "presentation_planning",
          status: "RUNNING",
          current_stage: "PRESENTATION_PLANNING",
          created_at: "2026-09-01T12:00:00Z",
          started_at: "2026-09-01T12:00:00Z",
          completed_at: null,
          result: {},
          error: null,
        };
      },
      pollIntervalMs: 50,
    },
  );

  await delay(150);
  assert.equal(harness.contentVisible(), true);
  assert.equal(harness.jobIndicatorVisible(), false);

  await delay(400);
  assert.equal(harness.jobIndicatorVisible(), true);
  assert.equal(harness.contentVisible(), true);
  cancel();
}

async function testDeckRefreshAfterJobCompletes(): Promise<void> {
  const harness = createHarness();
  let loadCount = 0;
  let pollCount = 0;

  const cancel = startPipelineParallelLoad(
    "deck",
    harness.handlers,
    {
      loadContent: async () => {
        loadCount += 1;
      },
      isMissingError: () => false,
      getActiveJob: async () => ({
        job_id: "job-2",
        job_type: "presentation_generation",
        status: "RUNNING",
        current_stage: "SLIDE_GENERATING",
        started_at: "2026-09-01T12:00:00Z",
        error: null,
      }),
      getJob: async () => {
        pollCount += 1;
        if (pollCount === 1) {
          return {
            job_id: "job-2",
            job_type: "presentation_generation",
            status: "RUNNING",
            current_stage: "SLIDE_GENERATING",
            created_at: "2026-09-01T12:00:00Z",
            started_at: "2026-09-01T12:00:00Z",
            completed_at: null,
            result: {},
            error: null,
          };
        }
        return {
          job_id: "job-2",
          job_type: "presentation_generation",
          status: "COMPLETED",
          current_stage: "PREVIEW_RENDERING",
          created_at: "2026-09-01T12:00:00Z",
          started_at: "2026-09-01T12:00:00Z",
          completed_at: "2026-09-01T12:05:00Z",
          result: {},
          error: null,
        };
      },
      pollIntervalMs: 20,
    },
  );

  await delay(250);
  assert.equal(loadCount, 2);
  assert.equal(harness.contentVisible(), true);
  assert.equal(harness.jobIndicatorVisible(), false);

  // BT-26: recovered jobs expose their real stage for the live progress panel.
  const recovered = harness.snapshots[0];
  assert.equal(recovered.jobType, "presentation_generation");
  assert.equal(recovered.currentStage, "SLIDE_GENERATING");
  assert.equal(
    buildJobProgressView({ snapshot: recovered })?.headline,
    "Generating slide content",
  );
  cancel();
}

async function testFailedJobPreservesValidationMetadata(): Promise<void> {
  const harness = createHarness();
  startPipelineParallelLoad("deck", harness.handlers, {
    loadContent: async () => {},
    isMissingError: () => false,
    getActiveJob: async () => ({
      job_id: "failed-job",
      job_type: "presentation_generation",
      status: "FAILED",
      current_stage: "SLIDE_VALIDATING",
      started_at: "2026-09-01T12:00:00Z",
      error: {
        code: "VALIDATION_FAILED",
        message: "Technical validation detail",
        stage: "SLIDE_VALIDATING",
        retryable: false,
      },
    }),
    getJob: async () => {
      throw new Error("not called");
    },
  });

  await delay(10);
  assert.deepEqual(harness.jobFailures[0], {
    code: "VALIDATION_FAILED",
    message: "Technical validation detail",
    stage: "SLIDE_VALIDATING",
    retryable: false,
    jobId: "failed-job",
  });
}

async function testLookupConnectionFailureIsReported(): Promise<void> {
  const harness = createHarness();
  startPipelineParallelLoad("framework", harness.handlers, {
    loadContent: async () => {},
    isMissingError: () => false,
    getActiveJob: async () => {
      throw new TypeError("Failed to fetch");
    },
    getJob: async () => {
      throw new Error("not called");
    },
  });

  await delay(10);
  assert.ok(harness.jobFailures[0] instanceof TypeError);
}

async function runTests(): Promise<void> {
  await testPlanLoadsIndependentlyOfJobPolling();
  await testDeckRefreshAfterJobCompletes();
  await testFailedJobPreservesValidationMetadata();
  await testLookupConnectionFailureIsReported();
  assert.equal(PIPELINE_JOB_POLL_MS, 2_500);
  console.log("pipelineParallelLoad tests passed");
}

void runTests();
