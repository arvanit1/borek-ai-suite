import { ApiRequestError } from "./api";

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
