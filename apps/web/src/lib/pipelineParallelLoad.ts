import type { ActiveJobResponse, JobResponse } from "./api";
import { formatJobFailureMessage } from "./jobErrors";
import {
  generationProgressMessage,
  inspectActiveJob,
  type ReconnectPage,
} from "./jobReconnect";

export const PIPELINE_JOB_POLL_MS = 2_500;

export interface PipelineParallelLoadHandlers {
  onContentLoaded: () => void;
  onContentMissing: () => void;
  onContentLoadFinished: () => void;
  onContentLoadError: (message: string) => void;
  onJobPollingStart: (message: string, stage: string | null, jobId: string) => void;
  onJobStageUpdate: (stage: string) => void;
  onJobPollingFinished: () => void;
  onJobFailed: (message: string, retryJobId: string | null) => void;
}

export interface PipelineParallelLoadDeps {
  loadContent: () => Promise<void>;
  isMissingError: (error: unknown) => boolean;
  getActiveJob: () => Promise<ActiveJobResponse | null>;
  getJob: (jobId: string) => Promise<JobResponse>;
  pollIntervalMs?: number;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function monitorJobUntilTerminal(
  jobId: string,
  deps: Pick<PipelineParallelLoadDeps, "getJob" | "pollIntervalMs">,
  onStageUpdate: (stage: string) => void,
  cancelled: () => boolean,
): Promise<JobResponse> {
  const intervalMs = deps.pollIntervalMs ?? PIPELINE_JOB_POLL_MS;
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

export function startPipelineParallelLoad(
  page: ReconnectPage,
  handlers: PipelineParallelLoadHandlers,
  deps: PipelineParallelLoadDeps,
): () => void {
  let cancelled = false;
  const isCancelled = () => cancelled;

  void deps
    .loadContent()
    .then(() => {
      if (!isCancelled()) {
        handlers.onContentLoaded();
      }
    })
    .catch((loadError) => {
      if (isCancelled()) {
        return;
      }
      if (deps.isMissingError(loadError)) {
        handlers.onContentMissing();
        return;
      }
      handlers.onContentLoadError(
        loadError instanceof Error ? loadError.message : "Could not load saved results.",
      );
    })
    .finally(() => {
      if (!isCancelled()) {
        handlers.onContentLoadFinished();
      }
    });

  void (async () => {
    try {
      const job = await deps.getActiveJob();
      if (isCancelled()) {
        return;
      }

      const decision = inspectActiveJob(job, page);
      if (decision.action === "monitor") {
        handlers.onJobPollingStart(
          generationProgressMessage(page, true),
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
          await deps.loadContent();
          if (isCancelled()) {
            return;
          }
          handlers.onContentLoaded();
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
      // Active-job lookup failure is non-fatal; saved content still renders.
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
