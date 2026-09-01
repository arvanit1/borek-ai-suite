import assert from "node:assert/strict";

import { formatJobFailureMessage } from "./jobErrors.js";

assert.equal(formatJobFailureMessage(null), "Generation job failed");

assert.match(
  formatJobFailureMessage({
    code: "PRESENTATION_PLAN_DUPLICATE_LAYOUTS",
    message: "Duplicate layouts (PROBLEM_SOLUTION_01).",
    stage: "PRESENTATION_PLANNING",
    retryable: false,
  }),
  /Duplicate layouts \(PROBLEM_SOLUTION_01\)/,
);

assert.match(
  formatJobFailureMessage({
    code: "PRESENTATION_PLANNING_FAILED",
    message:
      "Invalid PresentationPlan: PresentationPlan layoutId values must be unique; duplicates: CONTEXT_01",
    stage: "PRESENTATION_PLANNING",
    retryable: true,
  }),
  /unique layout/,
);
assert.match(
  formatJobFailureMessage({
    code: "PRESENTATION_PLANNING_FAILED",
    message:
      "Invalid PresentationPlan: PresentationPlan layoutId values must be unique; duplicates: CONTEXT_01",
    stage: "PRESENTATION_PLANNING",
    retryable: true,
  }),
  /CONTEXT_01/,
);

console.log("jobErrors tests passed");
