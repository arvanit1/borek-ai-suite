import assert from "node:assert/strict";

import type { JobResponse } from "./api.js";
import type { FrameworkVersionResponse } from "./frameworkTypes.js";
import {
  FRAMEWORK_REVIEW_JOB_POLL_MS,
  startFrameworkReviewParallelLoad,
  type FrameworkReviewLoadHandlers,
} from "./frameworkReviewLoad.js";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const sampleFramework = {
  id: "fw-1",
  opportunity_id: "opp-1",
  version_number: 1,
  status: "confirmed",
  framework_json: {
    schema_version: "1.0",
    opportunity_id: "opp-1",
    title: "Invoice Automation",
    department: "Finance",
    status: "confirmed",
    chapters: [],
  },
  created_at: "2026-09-01T12:00:00Z",
  updated_at: "2026-09-01T12:00:00Z",
} as unknown as FrameworkVersionResponse;

const runningJob = {
  job_id: "job-1",
  job_type: "framework_generation",
  status: "RUNNING" as const,
  current_stage: "FRAMEWORK_SYNTHESIZING",
  started_at: "2026-09-01T12:00:00Z",
  error: null,
};

function completedJobResponse(): JobResponse {
  return {
    job_id: "job-1",
    job_type: "framework_generation",
    status: "COMPLETED",
    current_stage: "FRAMEWORK_COMPLETE",
    created_at: "2026-09-01T12:00:00Z",
    started_at: "2026-09-01T12:00:00Z",
    completed_at: "2026-09-01T12:05:00Z",
    result: {},
    error: null,
  };
}

function createHarness() {
  let framework: FrameworkVersionResponse | null = null;
  let frameworkLoading = true;
  let jobPolling = false;
  const events: string[] = [];

  const handlers: FrameworkReviewLoadHandlers = {
    onFrameworkLoaded: (loaded) => {
      framework = loaded;
      events.push("framework_loaded");
    },
    onFrameworkMissing: () => {
      framework = null;
      events.push("framework_missing");
    },
    onFrameworkLoadFinished: () => {
      frameworkLoading = false;
      events.push("framework_load_finished");
    },
    onFrameworkLoadError: () => {
      frameworkLoading = false;
      events.push("framework_load_error");
    },
    onJobPollingStart: () => {
      jobPolling = true;
      events.push("job_polling_start");
    },
    onJobStageUpdate: () => {
      events.push("job_stage_update");
    },
    onJobPollingFinished: () => {
      jobPolling = false;
      events.push("job_polling_finished");
    },
    onJobFailed: () => {
      events.push("job_failed");
    },
  };

  return {
    handlers,
    frameworkVisible: () => framework !== null,
    jobIndicatorVisible: () => jobPolling,
    events,
  };
}

async function testFrameworkLoadsIndependentlyOfJobPolling(): Promise<void> {
  const harness = createHarness();
  let frameworkFetches = 0;

  let jobPollCount = 0;

  const cancel = startFrameworkReviewParallelLoad(harness.handlers, {
    loadFramework: async () => {
      frameworkFetches += 1;
      await delay(100);
      return sampleFramework;
    },
    getActiveJob: async () => {
      await delay(500);
      return runningJob;
    },
    getJob: async () => {
      jobPollCount += 1;
      await delay(100);
      return { ...completedJobResponse(), status: "RUNNING" };
    },
    pollIntervalMs: 50,
  });

  await delay(150);
  assert.equal(harness.frameworkVisible(), true, "framework should render after fast fetch");
  assert.equal(harness.jobIndicatorVisible(), false, "job indicator should not appear yet");

  await delay(400);
  assert.equal(harness.jobIndicatorVisible(), true, "job indicator should appear after slow job fetch");
  assert.equal(harness.frameworkVisible(), true, "framework must stay visible while job polls");
  assert.ok(
    harness.events.indexOf("framework_loaded") < harness.events.indexOf("job_polling_start"),
    "framework must load before job polling starts",
  );
  assert.equal(frameworkFetches >= 1, true);
  cancel();
}

async function testFrameworkShownWhenJobIsRunning(): Promise<void> {
  const harness = createHarness();

  const cancel = startFrameworkReviewParallelLoad(harness.handlers, {
    loadFramework: async () => sampleFramework,
    getActiveJob: async () => runningJob,
    getJob: async () => {
      await delay(500);
      return { ...completedJobResponse(), status: "RUNNING" };
    },
    pollIntervalMs: 1_000,
  });

  await delay(80);
  assert.equal(harness.frameworkVisible(), true);
  assert.equal(harness.jobIndicatorVisible(), true);
  cancel();
}

async function testFrameworkRefreshAfterJobCompletes(): Promise<void> {
  const harness = createHarness();
  let frameworkFetches = 0;
  let pollCount = 0;

  const cancel = startFrameworkReviewParallelLoad(harness.handlers, {
    loadFramework: async () => {
      frameworkFetches += 1;
      return sampleFramework;
    },
    getActiveJob: async () => runningJob,
    getJob: async () => {
      pollCount += 1;
      if (pollCount === 1) {
        return { ...completedJobResponse(), status: "RUNNING" };
      }
      return completedJobResponse();
    },
    pollIntervalMs: 20,
  });

  await delay(250);
  assert.equal(frameworkFetches, 2, "framework should refresh once after job completion");
  assert.equal(harness.frameworkVisible(), true, "framework stays visible through completion");
  assert.equal(harness.jobIndicatorVisible(), false, "job indicator clears after completion");
  assert.ok(harness.events.includes("job_polling_finished"));
  assert.ok(!harness.events.includes("framework_missing"));
  cancel();
}

async function runTests(): Promise<void> {
  await testFrameworkLoadsIndependentlyOfJobPolling();
  await testFrameworkShownWhenJobIsRunning();
  await testFrameworkRefreshAfterJobCompletes();

  assert.equal(FRAMEWORK_REVIEW_JOB_POLL_MS, 2_500);

  console.log("frameworkReviewLoad tests passed");
}

void runTests();
