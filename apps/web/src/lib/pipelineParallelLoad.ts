import type { ActiveJobResponse, JobResponse } from "./api";
import {
  snapshotFromActiveJob,
  snapshotFromJob,
  type JobProgressSnapshot,
} from "./jobProgress";
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
  onJobFailed: (error: unknown, retryJobId: string | null) => void;
  /** Real job state for live progress; optional so existing callers are unaffected. */
  onJobSnapshot?: (snapshot: JobProgressSnapshot) => void;
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
  onStageUpdate: (stage: string, job: JobResponse) => void,
  cancelled: () => boolean,
): Promise<JobResponse> {
  const intervalMs = deps.pollIntervalMs ?? PIPELINE_JOB_POLL_MS;
  while (!cancelled()) {
    const job = await deps.getJob(jobId);
    onStageUpdate(job.current_stage, job);
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
        if (job) {
          handlers.onJobSnapshot?.(snapshotFromActiveJob(job));
        }
        try {
          await monitorJobUntilTerminal(
            decision.jobId,
            deps,
            (stage, polled) => {
              if (!isCancelled()) {
                handlers.onJobStageUpdate(stage);
                handlers.onJobSnapshot?.(snapshotFromJob(polled));
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
            handlers.onJobSnapshot?.(snapshotFromJob(monitorError));
            const retryable = Boolean(monitorError.error?.retryable);
            handlers.onJobFailed(
              {
                ...monitorError.error,
                jobId: monitorError.job_id,
              },
              retryable ? monitorError.job_id : null,
            );
          } else {
            handlers.onJobFailed(monitorError, null);
          }
        }
        return;
      }

      if (decision.action === "failed") {
        if (job) {
          handlers.onJobSnapshot?.(snapshotFromActiveJob(job));
        }
        handlers.onJobFailed(
          {
            ...decision.error,
            jobId: decision.jobId,
          },
          decision.retryable ? decision.jobId : null,
        );
      }
    } catch (error) {
      if (!isCancelled()) {
        handlers.onJobFailed(error, null);
      }
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
