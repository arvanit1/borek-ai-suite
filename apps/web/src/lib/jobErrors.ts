import type { JobErrorDetail } from "./api";

const DUPLICATE_LAYOUT_PATTERN =
  /layoutId values must be unique;\s*duplicates:\s*(.+?)(?:\)|$)/i;

/** AT-42/45: surface duplicate-layout planner failures with actionable copy. */
export function formatJobFailureMessage(error: JobErrorDetail | null | undefined): string {
  if (!error?.message) {
    return "Generation job failed";
  }
  if (error.code === "PRESENTATION_PLAN_DUPLICATE_LAYOUTS") {
    return error.message;
  }
  const match = error.message.match(DUPLICATE_LAYOUT_PATTERN);
  if (match) {
    const duplicates = match[1].trim().replace(/\.$/, "");
    return (
      `The AI planner assigned the same slide layout more than once (${duplicates}). ` +
      "Each slide must use a unique layout. Try Generate plan again; if the error persists, " +
      "the planning prompt needs adjustment (BT-1)."
    );
  }
  if (error.message.startsWith("Invalid PresentationPlan:")) {
    return `Presentation plan validation failed: ${error.message.replace(/^Invalid PresentationPlan:\s*/, "")}`;
  }
  return error.message;
}
