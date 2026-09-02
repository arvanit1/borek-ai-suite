import { customerStatusLabel } from "./frameworkLabels";

export const REVIEW_STATE_READY = "READY_TO_APPROVE";
export const REVIEW_STATE_RECOMMENDED = "REVIEW_RECOMMENDED";
export const REVIEW_STATE_BLOCKING = "BLOCKING_CONTRADICTION";
export const REVIEW_STATE_MISSING = "MISSING_REQUIRED_INFORMATION";
export const REVIEW_STATE_WEAK_EVIDENCE = "WEAK_EVIDENCE";

export type ReviewState =
  | typeof REVIEW_STATE_READY
  | typeof REVIEW_STATE_RECOMMENDED
  | typeof REVIEW_STATE_BLOCKING
  | typeof REVIEW_STATE_MISSING
  | typeof REVIEW_STATE_WEAK_EVIDENCE
  | string;

export type AttentionSeverity = "blocking" | "warning" | "info" | string;

export interface ReviewOpenItem {
  item_type?: string | null;
  description?: string | null;
  owner?: string | null;
  status?: string | null;
  chapter_id?: string | null;
}

export interface ReviewBlockingItem {
  kind?: string | null;
  chapter_id?: string | null;
  message: string;
}

export interface ReviewEvidenceWarning {
  chapter_id?: string | null;
  title?: string | null;
  message: string;
}

export interface ReviewReadiness {
  band?: string | null;
  status_label?: string | null;
  build_readiness?: number | null;
  conversation_quality?: number | null;
  opportunity_rating?: number | null;
  render_allowed?: boolean | null;
  assumptions_banner?: boolean | null;
}

export interface ReviewSummary {
  language?: string | null;
  headline?: string | null;
  executive_summary?: string | null;
  key_pain_points?: string[];
  key_requirements?: string[];
  target_outcomes?: string[];
  assumptions?: ReviewOpenItem[];
  open_questions?: ReviewOpenItem[];
  contradictions?: ReviewOpenItem[];
  evidence_warnings?: ReviewEvidenceWarning[];
  readiness?: ReviewReadiness | null;
  blocking_items?: ReviewBlockingItem[];
  confirm_ready?: boolean | null;
  confirm_block_reason?: string | null;
}

export interface AttentionSignal {
  id: string;
  severity: AttentionSeverity;
  message: string;
  action?: string | null;
  chapter_id?: string | null;
  fields?: string[];
  count?: number | null;
}

export interface AttentionBundle {
  review_state: ReviewState;
  signals: AttentionSignal[];
}

export interface FrameworkReviewPayload {
  review_summary: ReviewSummary;
  attention?: AttentionBundle | null;
  attention_signals: AttentionSignal[];
  review_state: ReviewState;
}

const BLOCKING_STATES = new Set([REVIEW_STATE_BLOCKING]);

export function isBlockingSignal(signal: AttentionSignal): boolean {
  return signal.severity === "blocking";
}

export function blockingSignals(signals: AttentionSignal[]): AttentionSignal[] {
  return signals.filter(isBlockingSignal);
}

export function reviewStateLabel(state: ReviewState | null | undefined): string {
  if (!state) {
    return "Needs review";
  }
  return customerStatusLabel(String(state));
}

export function attentionTone(
  state: ReviewState | null | undefined,
  signals: AttentionSignal[],
): "blocking" | "warning" | "ready" | "info" {
  if (isApprovalBlocked({ review_state: state ?? "", attention_signals: signals, review_summary: {} })) {
    return "blocking";
  }
  if (state === REVIEW_STATE_RECOMMENDED || signals.some((signal) => signal.severity === "warning")) {
    return "warning";
  }
  if (state === REVIEW_STATE_READY) {
    return "ready";
  }
  return "info";
}

export function isApprovalBlocked(payload: {
  review_state?: ReviewState | null;
  attention_signals?: AttentionSignal[] | null;
  review_summary?: ReviewSummary | null;
}): boolean {
  const signals = payload.attention_signals ?? [];
  if (signals.some(isBlockingSignal)) {
    return true;
  }
  const state = payload.review_state ?? "";
  if (BLOCKING_STATES.has(state)) {
    return true;
  }
  const summary = payload.review_summary;
  if (summary?.confirm_ready === false) {
    return true;
  }
  if ((summary?.blocking_items ?? []).length > 0 && state !== REVIEW_STATE_RECOMMENDED && state !== REVIEW_STATE_READY) {
    return true;
  }
  return false;
}

export function canApproveAndBuild(options: {
  editable: boolean;
  confirmed: boolean;
  humanConfirmed: boolean;
  blocked: boolean;
}): boolean {
  return options.editable && !options.confirmed && options.humanConfirmed && !options.blocked;
}

export function openItemText(item: ReviewOpenItem): string {
  return String(item.description ?? "").trim();
}

export function evidenceWarningText(warning: ReviewEvidenceWarning): string {
  const title = String(warning.title ?? "").trim();
  const chapter = String(warning.chapter_id ?? "").trim();
  if (title && chapter) {
    return `${title} (chapter ${chapter}) has no cited sources.`;
  }
  if (title) {
    return `${title} has no cited sources.`;
  }
  if (chapter) {
    return `Chapter ${chapter} has no cited sources.`;
  }
  return warning.message.replace(/source references/gi, "cited sources");
}

export function reviewPayloadFromUnknown(value: unknown): FrameworkReviewPayload | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const record = value as Record<string, unknown>;
  const nestedJson =
    typeof record.framework_json === "object" && record.framework_json !== null
      ? (record.framework_json as Record<string, unknown>)
      : record;
  const summary = (record.review_summary ?? nestedJson.review_summary) as ReviewSummary | undefined;
  if (!summary || typeof summary !== "object") {
    return null;
  }
  const attention = (record.attention ?? nestedJson.attention) as AttentionBundle | undefined;
  const signals = Array.isArray(record.attention_signals)
    ? (record.attention_signals as AttentionSignal[])
    : Array.isArray(nestedJson.attention_signals)
      ? (nestedJson.attention_signals as AttentionSignal[])
      : attention?.signals ?? [];
  const reviewState =
    (typeof record.review_state === "string" && record.review_state) ||
    (typeof nestedJson.review_state === "string" && nestedJson.review_state) ||
    attention?.review_state ||
    REVIEW_STATE_RECOMMENDED;
  return {
    review_summary: summary,
    attention: attention ?? { review_state: reviewState, signals },
    attention_signals: signals,
    review_state: reviewState,
  };
}

export const HUMAN_CONFIRM_LABEL =
  "I have reviewed this customer story and I approve building the presentation.";

export const APPROVE_BUILD_LABEL = "Approve & build presentation";
