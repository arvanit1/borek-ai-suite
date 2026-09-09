import assert from "node:assert/strict";

import { ApiRequestError } from "./api.js";
import {
  inputRequiredRecoveryNotice,
  recoveryActionHref,
  recoveryNoticeFromError,
  recoverySurfacePrecedence,
  retryingRecoveryNotice,
} from "./recoveryUx.js";

const connection = recoveryNoticeFromError(new TypeError("Failed to fetch"), "deck");
assert.equal(connection.category, "CONNECTION_LOST");
assert.equal(connection.action?.kind, "RECONNECT");
assert.doesNotMatch(connection.message, /failed to fetch/i);

const running = recoveryNoticeFromError(
  new ApiRequestError("Generation job timed out", 408, "JOB_TIMEOUT", { jobId: "job-1" }),
  "framework",
);
assert.equal(running.category, "STILL_RUNNING");
assert.equal(running.action?.kind, "KEEP_CHECKING");
assert.equal(running.technical?.jobId, "job-1");

const retrying = retryingRecoveryNotice("plan", "job-2");
assert.equal(retrying.category, "RETRYING");
assert.equal(retrying.action, undefined);

const input = inputRequiredRecoveryNotice("framework");
assert.equal(input.category, "INPUT_REQUIRED");
assert.equal(input.action?.kind, "UPLOAD");

const validation = recoveryNoticeFromError(
  new ApiRequestError("Raw validator output", 422, "VALIDATION_FAILED", {
    retryable: true,
    jobId: "job-3",
    stage: "SLIDE_VALIDATING",
  }),
  "deck",
);
assert.equal(validation.category, "VALIDATION_NEEDS_REVIEW");
assert.equal(validation.action?.kind, "REVIEW");
assert.equal(validation.action?.target, "plan");
assert.notEqual(validation.action?.kind, "RETRY");
assert.doesNotMatch(validation.message, /raw validator/i);
assert.equal(validation.technical?.message, "Raw validator output");

const duplicatePlan = recoveryNoticeFromError(
  new ApiRequestError(
    "The presentation plan contains duplicate layouts.",
    422,
    "PRESENTATION_PLAN_DUPLICATE_LAYOUTS",
    { retryable: false, jobId: "job-plan", stage: "PRESENTATION_PLANNING" },
  ),
  "plan",
);
assert.equal(duplicatePlan.category, "VALIDATION_NEEDS_REVIEW");
assert.equal(duplicatePlan.action?.label, "Generate plan again");
assert.equal(duplicatePlan.action?.target, "plan");
assert.equal(
  recoveryActionHref(duplicatePlan, "opportunity-1"),
  "/plan-preview?opportunityId=opportunity-1",
);

const liveCoverValidation = recoveryNoticeFromError(
  new ApiRequestError(
    "COVER_01 generation failed validation: Slide (COVER_01) Field statBadges item count 4 exceeds maximum 3",
    422,
    "PRESENTATION_GENERATION_FAILED",
    { retryable: false, jobId: "job-cover", stage: "SLIDE_GENERATING" },
  ),
  "deck",
);
assert.equal(liveCoverValidation.category, "VALIDATION_NEEDS_REVIEW");
assert.equal(liveCoverValidation.action?.kind, "REVIEW");
assert.doesNotMatch(liveCoverValidation.message, /COVER_01|statBadges/i);

const retryableFailure = recoveryNoticeFromError(
  new ApiRequestError("Provider response body", 422, "PROVIDER_UNAVAILABLE", {
    retryable: true,
    jobId: "job-4",
    stage: "PRESENTATION_PLANNING",
  }),
  "plan",
);
assert.equal(retryableFailure.category, "TERMINAL_FAILURE");
assert.equal(retryableFailure.action?.kind, "RETRY");
assert.doesNotMatch(retryableFailure.message, /provider response/i);

const terminalFailure = recoveryNoticeFromError(
  new ApiRequestError("Internal worker path", 422, "GENERATION_FAILED", {
    retryable: false,
    jobId: "job-5",
  }),
  "framework",
);
assert.equal(terminalFailure.category, "TERMINAL_FAILURE");
assert.equal(terminalFailure.action?.kind, "RECENT");

const frameworkInput = recoveryNoticeFromError(
  new ApiRequestError("Framework must be confirmed", 409, "FRAMEWORK_NOT_CONFIRMED"),
  "deck",
);
assert.equal(frameworkInput.action?.target, "framework");
assert.equal(
  recoveryActionHref(frameworkInput, "opportunity-1"),
  "/framework-review?opportunityId=opportunity-1",
);

assert.deepEqual(recoverySurfacePrecedence(running, true), {
  showRecovery: false,
  showProgress: true,
  showSecondary: false,
});
assert.deepEqual(recoverySurfacePrecedence(validation, true), {
  showRecovery: true,
  showProgress: false,
  showSecondary: false,
});
assert.deepEqual(recoverySurfacePrecedence(null, false), {
  showRecovery: false,
  showProgress: false,
  showSecondary: true,
});
assert.equal(
  recoveryActionHref(validation, "opportunity-1"),
  "/plan-preview?opportunityId=opportunity-1",
);

const gammaCases = [
  ["GAMMA_TIMEOUT", true, "TERMINAL_FAILURE", "RETRY"],
  ["GAMMA_AUTH", false, "TERMINAL_FAILURE", undefined],
  ["GAMMA_TEMPLATE_LOCKED", false, "TERMINAL_FAILURE", undefined],
  ["GAMMA_PAYLOAD_INVALID", false, "VALIDATION_NEEDS_REVIEW", "REVIEW"],
  ["GAMMA_RATE_LIMIT", true, "TERMINAL_FAILURE", "RETRY"],
  ["GAMMA_PROVIDER_FAILED", true, "TERMINAL_FAILURE", "RETRY"],
] as const;

for (const [code, retryable, category, action] of gammaCases) {
  const notice = recoveryNoticeFromError(
    new ApiRequestError("Provider details", 422, code, {
      retryable,
      jobId: "job-provider",
      stage: "GAMMA_RENDERING",
    }),
    "deck",
  );
  assert.equal(notice.category, category, code);
  assert.equal(notice.action?.kind, action, code);
  assert.doesNotMatch(`${notice.title} ${notice.message} ${notice.action?.label ?? ""}`, /gamma/i);
}

const payloadRejected = recoveryNoticeFromError(
  new ApiRequestError("Payload details", 422, "GAMMA_PAYLOAD_INVALID", {
    retryable: false,
    jobId: "job-payload",
  }),
  "deck",
);
assert.equal(payloadRejected.action?.target, "framework");

const interruptedWhileRunning = recoveryNoticeFromError(
  new TypeError("Failed to fetch"),
  "deck",
  { knownRunning: true },
);
assert.equal(interruptedWhileRunning.category, "STILL_RUNNING");
assert.equal(interruptedWhileRunning.action?.kind, "KEEP_CHECKING");

console.log("recoveryUx tests passed");
