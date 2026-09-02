import type { ActiveJobResponse, JobResponse } from "./api";
import { isMissingFrameworkError } from "./apiErrors";
import type { FrameworkVersionResponse } from "./frameworkTypes";
import { formatJobFailureMessage } from "./jobErrors";
import { generationProgressMessage, inspectActiveJob } from "./jobReconnect";

export const FRAMEWORK_REVIEW_JOB_POLL_MS = 2_500;

export interface FrameworkReviewLoadHandlers {
  onFrameworkLoaded: (framework: FrameworkVersionResponse) => void;
  onFrameworkMissing: () => void;
  onFrameworkLoadFinished: () => void;
  onFrameworkLoadError: (message: string) => void;
  onJobPollingStart: (message: string, stage: string | null, jobId: string) => void;
  onJobStageUpdate: (stage: string) => void;
  onJobPollingFinished: () => void;
  onJobFailed: (message: string, retryJobId: string | null) => void;
}

export interface FrameworkReviewLoadDeps {
  loadFramework: () => Promise<FrameworkVersionResponse>;
  getActiveJob: () => Promise<ActiveJobResponse | null>;
  getJob: (jobId: string) => Promise<JobResponse>;
  pollIntervalMs?: number;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function monitorJobUntilTerminal(
  jobId: string,
  deps: Pick<FrameworkReviewLoadDeps, "getJob" | "pollIntervalMs">,
  onStageUpdate: (stage: string) => void,
  cancelled: () => boolean,
): Promise<JobResponse> {
  const intervalMs = deps.pollIntervalMs ?? FRAMEWORK_REVIEW_JOB_POLL_MS;
  while (!cancelled()) {
    const job = await deps.getJob(jobId);
    onStageUpdate(job.current_stage);
    if (job.status === "COMPLETED") {
      return job;
    }
    if (job.status === "FAILED") {
      throw job;
    }
    await sleep(intervalMs);
  }
  throw new Error("Job monitoring cancelled");
}

export function startFrameworkReviewParallelLoad(
  handlers: FrameworkReviewLoadHandlers,
  deps: FrameworkReviewLoadDeps,
): () => void {
  let cancelled = false;
  const isCancelled = () => cancelled;

  void deps
    .loadFramework()
    .then((framework) => {
      if (isCancelled()) {
        return;
      }
      handlers.onFrameworkLoaded(framework);
    })
    .catch((loadError) => {
      if (isCancelled()) {
        return;
      }
      if (isMissingFrameworkError(loadError)) {
        handlers.onFrameworkMissing();
        return;
      }
      handlers.onFrameworkLoadError(
        loadError instanceof Error ? loadError.message : "Could not load framework.",
      );
    })
    .finally(() => {
      if (!isCancelled()) {
        handlers.onFrameworkLoadFinished();
      }
    });

  void (async () => {
    try {
      const job = await deps.getActiveJob();
      if (isCancelled()) {
        return;
      }

      const decision = inspectActiveJob(job, "framework");
      if (decision.action === "monitor") {
        handlers.onJobPollingStart(
          generationProgressMessage("framework", true),
          job?.current_stage ?? null,
          decision.jobId,
        );
        try {
          await monitorJobUntilTerminal(
            decision.jobId,
            deps,
            (stage) => {
              if (!isCancelled()) {
                handlers.onJobStageUpdate(stage);
              }
            },
            isCancelled,
          );
          if (isCancelled()) {
            return;
          }
          handlers.onJobPollingFinished();
          const refreshed = await deps.loadFramework();
          if (isCancelled()) {
            return;
          }
          handlers.onFrameworkLoaded(refreshed);
        } catch (monitorError) {
          if (isCancelled()) {
            return;
          }
          handlers.onJobPollingFinished();
          if (isFailedJobResponse(monitorError)) {
            const message = formatJobFailureMessage(monitorError.error);
            const retryable = Boolean(monitorError.error?.retryable);
            handlers.onJobFailed(message, retryable ? monitorError.job_id : null);
          } else if (monitorError instanceof Error) {
            handlers.onJobFailed(monitorError.message, null);
          } else {
            handlers.onJobFailed("Generation job failed.", null);
          }
        }
        return;
      }

      if (decision.action === "failed") {
        handlers.onJobFailed(
          decision.message,
          decision.retryable ? decision.jobId : null,
        );
      }
    } catch {
      // Active-job lookup failure is non-fatal; saved framework still renders.
    }
  })();

  return () => {
    cancelled = true;
  };
}

function isFailedJobResponse(value: unknown): value is JobResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    (value as JobResponse).status === "FAILED"
  );
}
