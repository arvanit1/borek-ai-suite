import type { ActiveJobResponse } from "./api";
import { formatJobFailureMessage } from "./jobErrors";

export type ReconnectPage = "framework" | "plan" | "deck";
export type JobStageGroup = "framework" | "presentation";

export type ReconnectDecision =
  | { action: "monitor"; jobId: string }
  | { action: "failed"; jobId: string; message: string; retryable: boolean }
  | { action: "load_results" };

const RUNNING_MESSAGES: Record<ReconnectPage, string> = {
  framework: "Framework generation is running…",
  plan: "Presentation planning is running…",
  deck: "Presentation rendering is running…",
};

const RESUME_MESSAGES: Record<ReconnectPage, string> = {
  framework: "Resuming framework generation…",
  plan: "Resuming presentation planning…",
  deck: "Resuming presentation rendering…",
};

export function stageGroupForPage(page: ReconnectPage): JobStageGroup {
  return page === "framework" ? "framework" : "presentation";
}

export function jobMatchesPage(jobType: string, page: ReconnectPage): boolean {
  const name = jobType.toLowerCase();
  if (page === "framework") {
    return name.includes("framework");
  }
  if (page === "plan") {
    return name.includes("plan");
  }
  return name.includes("presentation_generation") || name.includes("slide");
}

export function isMonitorableJobStatus(status: string): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

export function jobFailureMessage(job: Pick<ActiveJobResponse, "error">): string {
  return formatJobFailureMessage(job.error ?? null);
}

export function inspectActiveJob(
  job: ActiveJobResponse | null,
  page: ReconnectPage,
): ReconnectDecision {
  if (!job || !jobMatchesPage(job.job_type, page)) {
    return { action: "load_results" };
  }
  if (isMonitorableJobStatus(job.status)) {
    return { action: "monitor", jobId: job.job_id };
  }
  if (job.status === "FAILED") {
    return {
      action: "failed",
      jobId: job.job_id,
      message: jobFailureMessage(job),
      retryable: Boolean(job.error?.retryable),
    };
  }
  return { action: "load_results" };
}

export function generationProgressMessage(page: ReconnectPage, existingJob: boolean): string {
  return existingJob ? RESUME_MESSAGES[page] : RUNNING_MESSAGES[page];
}
