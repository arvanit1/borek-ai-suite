import { ApiRequestError } from "./api";

export function isMissingOpportunityError(error: unknown): boolean {
  if (!(error instanceof ApiRequestError)) {
    return false;
  }
  return error.status === 404 || error.code === "NOT_FOUND" || error.code === "OPPORTUNITY_NOT_FOUND";
}

export function isMissingFrameworkError(error: unknown): boolean {
  if (!(error instanceof ApiRequestError)) {
    return false;
  }
  return error.status === 404 || error.code === "FRAMEWORK_NOT_FOUND";
}

export function isMissingPresentationPlanError(error: unknown): boolean {
  if (!(error instanceof ApiRequestError)) {
    return false;
  }
  return error.status === 404 || error.code === "PRESENTATION_PLAN_NOT_FOUND";
}

export function isMissingPresentationError(error: unknown): boolean {
  if (!(error instanceof ApiRequestError)) {
    return false;
  }
  return error.status === 404 || error.code === "PRESENTATION_NOT_FOUND";
}

export function isMissingActiveJobError(error: unknown): boolean {
  if (!(error instanceof ApiRequestError)) {
    return false;
  }
  return error.status === 404 || error.code === "ACTIVE_JOB_NOT_FOUND";
}

export function isPresentationNotReadyError(error: unknown): boolean {
  if (!(error instanceof ApiRequestError)) {
    return false;
  }
  return error.code === "PRESENTATION_NOT_READY";
}

export function isDeckFileMissingError(error: unknown): boolean {
  if (!(error instanceof ApiRequestError)) {
    return false;
  }
  return error.status === 404 || error.code === "DECK_FILE_NOT_FOUND" || error.code === "SLIDE_PREVIEW_NOT_FOUND";
}

function isNetworkError(error: unknown): boolean {
  return (
    error instanceof TypeError ||
    (error instanceof Error &&
      /failed to fetch|networkerror|network request failed|load failed/i.test(error.message))
  );
}

export function opportunityErrorMessage(error: unknown): string {
  if (isNetworkError(error)) {
    return "The connection was interrupted. Check your network and try creating the opportunity again.";
  }
  if (error instanceof ApiRequestError && (error.status === 401 || error.status === 403)) {
    return "Your session could not be verified. Sign in again and retry.";
  }
  if (error instanceof ApiRequestError && error.status === 400) {
    return "Check the opportunity details and try again.";
  }
  return "The opportunity could not be created. Try again or contact support if this continues.";
}

export function uploadErrorMessage(error: unknown): string {
  if (isNetworkError(error)) {
    return "Upload interrupted. Check your connection and try this file again.";
  }
  if (error instanceof ApiRequestError) {
    if (error.status === 401 || error.status === 403) {
      return "Your session could not be verified. Sign in again before uploading.";
    }
    if (error.status === 413) {
      return "This file is too large to upload.";
    }
    if (error.code === "INVALID_TRANSCRIPT_FORMAT") {
      return "This file format is not supported. Use TXT, VTT, SRT, or DOCX.";
    }
    if (error.code === "INVALID_TRANSCRIPT_CONTENT") {
      return "This transcript could not be read. Check the file contents and try again.";
    }
  }
  return "This transcript could not be uploaded. Remove it and try again.";
}
