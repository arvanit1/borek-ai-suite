import type { JobErrorDetail } from "./api";

export type RecoveryCategory =
  | "CONNECTION_LOST"
  | "STILL_RUNNING"
  | "RETRYING"
  | "INPUT_REQUIRED"
  | "VALIDATION_NEEDS_REVIEW"
  | "TERMINAL_FAILURE";

export type RecoveryContext = "framework" | "plan" | "deck";

export interface RecoveryAction {
  kind: "RECONNECT" | "KEEP_CHECKING" | "REVIEW" | "RETRY" | "RECENT" | "UPLOAD";
  label: string;
  href?: string;
  target?: "framework" | "plan";
}

export interface RecoveryNotice {
  category: RecoveryCategory;
  title: string;
  message: string;
  action?: RecoveryAction;
  technical?: {
    code?: string;
    stage?: string;
    jobId?: string;
    message?: string;
  };
}

interface ErrorShape {
  code?: string;
  stage?: string;
  jobId?: string;
  retryable?: boolean;
  message?: string;
}

const VALIDATION_CODES = new Set([
  "CONTENT_CONSTRAINT_EXCEEDED",
  "PRESENTATION_PLAN_DUPLICATE_LAYOUTS",
  "PRESENTATION_PLAN_VALIDATION_FAILED",
  "RENDER_VALIDATION_FAILED",
  "VALIDATION_FAILED",
]);

const INPUT_CODES = new Set([
  "FRAMEWORK_NOT_CONFIRMED",
  "FRAMEWORK_REQUIRED",
  "NO_TRANSCRIPTS",
  "TRANSCRIPT_REQUIRED",
  "TRANSCRIPTS_REQUIRED",
]);

const COPY: Record<RecoveryContext, { subject: string; running: string }> = {
  framework: {
    subject: "framework",
    running: "Your framework is still being prepared. You can safely leave this page and return later.",
  },
  plan: {
    subject: "presentation plan",
    running: "Your presentation plan is still being prepared. You can safely leave this page and return later.",
  },
  deck: {
    subject: "presentation",
    running: "Your presentation is still being prepared. You can safely leave this page and return later.",
  },
};

function errorShape(error: unknown): ErrorShape {
  if (!error || typeof error !== "object") {
    return {};
  }
  const value = error as ErrorShape;
  return {
    code: value.code,
    stage: value.stage,
    jobId: value.jobId,
    retryable: value.retryable,
    message: typeof value.message === "string" ? value.message : undefined,
  };
}

function supportDetails(error: unknown, fallback?: Partial<ErrorShape>) {
  const value = { ...fallback, ...errorShape(error) };
  return {
    code: value.code,
    stage: value.stage,
    jobId: value.jobId,
    message: value.message,
  };
}

function isConnectionError(error: unknown): boolean {
  const value = errorShape(error);
  return (
    error instanceof TypeError ||
    value.code === "NETWORK_ERROR" ||
    /failed to fetch|networkerror|network request failed|load failed/i.test(value.message ?? "")
  );
}

function isValidationError(value: ErrorShape): boolean {
  return (
    (value.code != null && VALIDATION_CODES.has(value.code)) ||
    value.stage === "FRAMEWORK_VALIDATING" ||
    value.stage === "SLIDE_VALIDATING"
  );
}

function reviewAction(context: RecoveryContext): RecoveryAction {
  if (context === "deck") {
    return { kind: "REVIEW", label: "Review presentation plan", target: "plan" };
  }
  return { kind: "REVIEW", label: "Review framework", target: "framework" };
}

export function runningRecoveryNotice(
  context: RecoveryContext,
  jobId?: string,
): RecoveryNotice {
  return {
    category: "STILL_RUNNING",
    title: "Work is still in progress",
    message: COPY[context].running,
    action: { kind: "KEEP_CHECKING", label: "Keep checking" },
    technical: jobId ? { jobId } : undefined,
  };
}

export function retryingRecoveryNotice(
  context: RecoveryContext,
  jobId?: string,
): RecoveryNotice {
  return {
    category: "RETRYING",
    title: "Trying again",
    message: `We are resuming your ${COPY[context].subject} from the last available stage.`,
    technical: jobId ? { jobId } : undefined,
  };
}

export function inputRequiredRecoveryNotice(
  context: RecoveryContext,
  message?: string,
): RecoveryNotice {
  const uploadRequired = context === "framework";
  return {
    category: "INPUT_REQUIRED",
    title: uploadRequired ? "A transcript is needed" : "Framework review is needed",
    message:
      message ??
      (uploadRequired
        ? "Upload at least one transcript before generating the framework."
        : "Confirm the framework before continuing with presentation generation."),
    action: uploadRequired
      ? { kind: "UPLOAD", label: "Upload transcripts" }
      : { kind: "REVIEW", label: "Review framework", target: "framework" },
  };
}

export function jobFailureRecoveryNotice(
  error: JobErrorDetail | null | undefined,
  context: RecoveryContext,
  jobId?: string,
): RecoveryNotice {
  return recoveryNoticeFromError(
    {
      code: error?.code,
      stage: error?.stage,
      retryable: error?.retryable,
      jobId,
      message: error?.message,
    },
    context,
  );
}

export function recoveryNoticeFromError(
  error: unknown,
  context: RecoveryContext,
  options: { connectionMessage?: string } = {},
): RecoveryNotice {
  const value = errorShape(error);
  const technical = supportDetails(error);

  if (value.code === "JOB_TIMEOUT") {
    return {
      ...runningRecoveryNotice(context, value.jobId),
      technical,
    };
  }

  if (isConnectionError(error)) {
    return {
      category: "CONNECTION_LOST",
      title: "Connection interrupted",
      message:
        options.connectionMessage ??
        `We could not check your ${COPY[context].subject}. Your work may still be running safely.`,
      action: { kind: "RECONNECT", label: "Reconnect" },
      technical,
    };
  }

  if (value.code != null && INPUT_CODES.has(value.code)) {
    return {
      ...inputRequiredRecoveryNotice(context),
      technical,
    };
  }

  if (isValidationError(value)) {
    return {
      category: "VALIDATION_NEEDS_REVIEW",
      title: "Review is needed before continuing",
      message: `Some ${COPY[context].subject} content needs attention before generation can continue.`,
      action: reviewAction(context),
      technical,
    };
  }

  return {
    category: "TERMINAL_FAILURE",
    title: `We could not complete your ${COPY[context].subject}`,
    message: value.retryable
      ? "The last stage can be tried again without starting over."
      : "Your saved work is available in Recent work. Try again later or contact support if this continues.",
    action:
      value.retryable && value.jobId
        ? { kind: "RETRY", label: "Try again" }
        : { kind: "RECENT", label: "Return to recent work", href: "/" },
    technical,
  };
}

export function recoveryActionHref(
  notice: RecoveryNotice,
  opportunityId: string,
): string | undefined {
  if (notice.action?.href) {
    return notice.action.href;
  }
  if (notice.action?.kind === "UPLOAD") {
    return `/upload?opportunityId=${opportunityId}`;
  }
  if (notice.action?.kind === "REVIEW") {
    const page = notice.action.target === "plan" ? "plan-preview" : "framework-review";
    return `/${page}?opportunityId=${opportunityId}`;
  }
  return undefined;
}
