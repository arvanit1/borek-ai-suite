import assert from "node:assert/strict";

import { formatJobFailureMessage } from "./jobErrors.js";
import { buildJobProgressView, jobStageLabel } from "./jobProgress.js";

// JJ-28: nothing a user reads on the way to "Your presentation is ready" may
// name the rendering engine.
const ENGINE_NAME = /gamma/i;

const providerFailures = [
  { code: "GAMMA_TIMEOUT", message: "Gamma generation timed out." },
  { code: "GAMMA_AUTH", message: "Gamma credentials are missing or rejected." },
  { code: "GAMMA_RATE_LIMIT", message: "Gamma rate-limited the request." },
  { code: "GAMMA_TEMPLATE_LOCKED", message: "The locked Gamma theme was not found." },
  { code: "GAMMA_PAYLOAD_INVALID", message: "Gamma rejected the generation payload." },
  { code: "GAMMA_PROVIDER_FAILED", message: "Gamma provider failed." },
];

for (const { code, message } of providerFailures) {
  const formatted = formatJobFailureMessage({
    code,
    message,
    stage: "GAMMA_RENDERING",
    retryable: true,
  });
  assert.doesNotMatch(formatted, ENGINE_NAME, `${code} leaked the engine name`);
  assert.ok(formatted.length > 0);
}

// An unmapped provider error still must not surface the engine name.
assert.doesNotMatch(
  formatJobFailureMessage({
    code: "SOMETHING_ELSE",
    message: "Gamma export download failed.",
    stage: "GAMMA_RENDERING",
    retryable: true,
  }),
  ENGINE_NAME,
);

// Unrelated failures keep their existing, more useful copy.
assert.match(
  formatJobFailureMessage({
    code: "PRESENTATION_PLAN_DUPLICATE_LAYOUTS",
    message: "Duplicate layouts (CONTEXT_01).",
    stage: "PRESENTATION_PLANNING",
    retryable: false,
  }),
  /CONTEXT_01/,
);

assert.doesNotMatch(jobStageLabel("GAMMA_RENDERING"), ENGINE_NAME);

const failedView = buildJobProgressView({
  snapshot: {
    jobId: "job-1",
    jobType: "presentation_generation",
    status: "FAILED",
    currentStage: "GAMMA_RENDERING",
    startedAt: null,
    createdAt: null,
    completedAt: null,
    error: {
      code: "GAMMA_TIMEOUT",
      message: "Gamma generation timed out.",
      stage: "GAMMA_RENDERING",
      retryable: true,
    },
  },
});
assert.ok(failedView);
assert.doesNotMatch(failedView.headline, ENGINE_NAME);
for (const step of failedView.steps) {
  assert.doesNotMatch(step.label, ENGINE_NAME);
}

// A stage failure with no message still names the stage, not the engine.
const bareView = buildJobProgressView({
  snapshot: {
    jobId: "job-2",
    jobType: "presentation_generation",
    status: "FAILED",
    currentStage: "PPTX_RENDERING",
    startedAt: null,
    createdAt: null,
    completedAt: null,
    error: null,
  },
});
assert.ok(bareView);
assert.match(bareView.headline, /Stopped at Rendering PowerPoint\/PDF/);

console.log("readyScreenEngineNeutral tests passed");
