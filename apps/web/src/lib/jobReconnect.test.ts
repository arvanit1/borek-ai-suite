import assert from "node:assert/strict";

import type { ActiveJobResponse } from "./api.js";
import {
  generationProgressMessage,
  inspectActiveJob,
  isMonitorableJobStatus,
  jobFailureMessage,
  jobMatchesPage,
  stageGroupForPage,
} from "./jobReconnect.js";

function job(overrides: Partial<ActiveJobResponse> = {}): ActiveJobResponse {
  return {
    job_id: "job-1",
    job_type: "framework_generation",
    status: "RUNNING",
    current_stage: "FRAMEWORK_SYNTHESIZING",
    started_at: "2026-09-01T12:00:00Z",
    error: null,
    ...overrides,
  };
}

assert.equal(stageGroupForPage("framework"), "framework");
assert.equal(stageGroupForPage("plan"), "presentation");
assert.equal(stageGroupForPage("deck"), "presentation");

assert.equal(jobMatchesPage("framework_generation", "framework"), true);
assert.equal(jobMatchesPage("framework_regenerate_chapter", "framework"), true);
assert.equal(jobMatchesPage("presentation_generation", "framework"), false);
assert.equal(jobMatchesPage("presentation_planning", "plan"), true);
assert.equal(jobMatchesPage("presentation_generation", "plan"), false);
assert.equal(jobMatchesPage("presentation_generation", "deck"), true);
assert.equal(jobMatchesPage("slide_regenerate", "deck"), true);
assert.equal(jobMatchesPage("presentation_planning", "deck"), false);

assert.equal(isMonitorableJobStatus("QUEUED"), true);
assert.equal(isMonitorableJobStatus("RUNNING"), true);
assert.equal(isMonitorableJobStatus("COMPLETED"), false);
assert.equal(isMonitorableJobStatus("FAILED"), false);

assert.deepEqual(inspectActiveJob(null, "framework"), { action: "load_results" });
assert.deepEqual(inspectActiveJob(job(), "framework"), {
  action: "monitor",
  jobId: "job-1",
});
assert.deepEqual(inspectActiveJob(job({ status: "QUEUED" }), "framework"), {
  action: "monitor",
  jobId: "job-1",
});
assert.deepEqual(inspectActiveJob(job({ status: "COMPLETED" }), "framework"), {
  action: "load_results",
});
assert.deepEqual(
  inspectActiveJob(
    job({
      status: "FAILED",
      error: {
        code: "GENERATION_FAILED",
        message: "Synthesis failed",
        stage: "FRAMEWORK_SYNTHESIZING",
        retryable: true,
      },
    }),
    "framework",
  ),
  {
    action: "failed",
    jobId: "job-1",
    message: "Synthesis failed",
    retryable: true,
  },
);
assert.deepEqual(
  inspectActiveJob(job({ job_type: "presentation_generation" }), "plan"),
  { action: "load_results" },
);
assert.deepEqual(
  inspectActiveJob(job({ job_type: "presentation_planning" }), "plan"),
  { action: "monitor", jobId: "job-1" },
);
assert.deepEqual(
  inspectActiveJob(job({ job_type: "presentation_planning" }), "deck"),
  { action: "load_results" },
);

assert.equal(jobFailureMessage({ error: null }), "Generation job failed");
assert.equal(
  generationProgressMessage("framework", false),
  "Framework generation is running…",
);
assert.equal(
  generationProgressMessage("framework", true),
  "Resuming framework generation…",
);
assert.equal(
  generationProgressMessage("plan", true),
  "Resuming presentation planning…",
);
assert.equal(
  generationProgressMessage("deck", true),
  "Resuming presentation rendering…",
);

console.log("jobReconnect tests passed");
