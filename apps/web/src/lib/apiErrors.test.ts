import assert from "node:assert/strict";

import { ApiRequestError } from "./api.js";
import {
  isMissingActiveJobError,
  isMissingFrameworkError,
  isMissingOpportunityError,
  isMissingPresentationError,
  isMissingPresentationPlanError,
  isPresentationNotReadyError,
  isDeckFileMissingError,
  opportunityErrorMessage,
  uploadErrorMessage,
  clientLogoErrorMessage,
  isMissingClientLogoError,
} from "./apiErrors.js";

assert.equal(
  isMissingFrameworkError(new ApiRequestError("No framework version exists", 404, "FRAMEWORK_NOT_FOUND")),
  true,
);
assert.equal(
  isMissingClientLogoError(new ApiRequestError("missing", 404, "CLIENT_LOGO_NOT_FOUND")),
  true,
);
assert.match(
  clientLogoErrorMessage(new ApiRequestError("raw", 400, "INVALID_CLIENT_LOGO_FORMAT")),
  /PNG, JPEG, or WebP/,
);
assert.match(
  clientLogoErrorMessage(new ApiRequestError("raw", 400, "INVALID_CLIENT_LOGO_CONTENT")),
  /could not be read/,
);
assert.match(
  clientLogoErrorMessage(new ApiRequestError("raw", 400, "CLIENT_LOGO_TOO_LARGE")),
  /5 MiB/,
);
assert.match(
  clientLogoErrorMessage(new ApiRequestError("raw", 400, "CLIENT_LOGO_DIMENSIONS_INVALID")),
  /64 and 4096 pixels/,
);
const rawServerError = new ApiRequestError(
  "Supabase response: relation transcripts does not exist",
  500,
  "TRANSCRIPT_CREATE_FAILED",
);
assert.doesNotMatch(clientLogoErrorMessage(rawServerError), /supabase|relation/i);
assert.equal(
  uploadErrorMessage(rawServerError),
  "This transcript could not be uploaded. Remove it and try again.",
);
assert.doesNotMatch(uploadErrorMessage(rawServerError), /supabase|relation/i);
assert.match(uploadErrorMessage(new TypeError("Failed to fetch")), /connection/i);
assert.match(
  uploadErrorMessage(new ApiRequestError("raw", 400, "INVALID_TRANSCRIPT_FORMAT")),
  /TXT, VTT, SRT, or DOCX/,
);
assert.doesNotMatch(opportunityErrorMessage(rawServerError), /supabase|relation/i);
assert.match(opportunityErrorMessage(new TypeError("Failed to fetch")), /connection/i);
assert.equal(isMissingOpportunityError(new ApiRequestError("Missing opportunity", 404, "NOT_FOUND")), true);
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
assert.equal(
  isPresentationNotReadyError(
    new ApiRequestError("Presentation is still generating", 409, "PRESENTATION_NOT_READY"),
  ),
  true,
);
assert.equal(isPresentationNotReadyError(new ApiRequestError("Missing presentation", 404)), false);
assert.equal(
  isDeckFileMissingError(new ApiRequestError("Deck pptx file is not available", 404, "DECK_FILE_NOT_FOUND")),
  true,
);

console.log("apiErrors tests passed");
