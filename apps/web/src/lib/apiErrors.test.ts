import assert from "node:assert/strict";

import { ApiRequestError } from "./api.js";
import {
  isMissingActiveJobError,
  isMissingFrameworkError,
  isMissingPresentationError,
  isMissingPresentationPlanError,
} from "./apiErrors.js";

assert.equal(
  isMissingFrameworkError(new ApiRequestError("No framework version exists", 404, "FRAMEWORK_NOT_FOUND")),
  true,
);
assert.equal(isMissingFrameworkError(new ApiRequestError("Server error", 500)), false);
assert.equal(
  isMissingPresentationPlanError(
    new ApiRequestError("No presentation plan exists", 404, "PRESENTATION_PLAN_NOT_FOUND"),
  ),
  true,
);
assert.equal(
  isMissingPresentationError(
    new ApiRequestError("No presentation exists", 404, "PRESENTATION_NOT_FOUND"),
  ),
  true,
);
assert.equal(
  isMissingActiveJobError(
    new ApiRequestError("No job found for this opportunity", 404, "ACTIVE_JOB_NOT_FOUND"),
  ),
  true,
);
assert.equal(isMissingActiveJobError(new ApiRequestError("Server error", 500)), false);

console.log("apiErrors tests passed");
