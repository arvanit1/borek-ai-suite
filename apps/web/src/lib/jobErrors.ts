import type { JobErrorDetail } from "./api";

const DUPLICATE_LAYOUT_PATTERN =
  /layoutId values must be unique;\s*duplicates:\s*(.+?)(?:\)|$)/i;

/**
 * JJ-28: the rendering engine is an implementation detail. Provider failures get
 * engine-neutral copy so the ready screen reads the same whichever engine ran.
 */
const RENDERING_ENGINE_MESSAGES: Record<string, string> = {
  GAMMA_TIMEOUT: "Building the branded presentation took too long. Try generating it again.",
  GAMMA_RATE_LIMIT: "The presentation service is busy right now. Try again in a few minutes.",
  GAMMA_PROVIDER_FAILED: "The presentation service could not finish the deck. Try again.",
  GAMMA_AUTH:
    "The presentation service rejected this request. Ask an administrator to check the setup.",
  GAMMA_TEMPLATE_LOCKED:
    "The branded template is unavailable. Ask an administrator to check the setup.",
  GAMMA_PAYLOAD_INVALID:
    "The presentation content was rejected while building the branded deck. Try again after " +
    "reviewing the Framework.",
};

const RENDERING_ENGINE_NAME_PATTERN = /\bgamma\b/i;

/** AT-42/45: surface duplicate-layout planner failures with actionable copy. */
export function formatJobFailureMessage(error: JobErrorDetail | null | undefined): string {
  const engineMessage = error?.code ? RENDERING_ENGINE_MESSAGES[error.code] : undefined;
  if (engineMessage) {
    return engineMessage;
  }
  if (!error?.message) {
    return "Generation job failed";
  }
  if (RENDERING_ENGINE_NAME_PATTERN.test(error.message)) {
    return RENDERING_ENGINE_MESSAGES.GAMMA_PROVIDER_FAILED;
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
