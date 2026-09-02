import type { FrameworkVersionResponse } from "./frameworkTypes";
import { isMissingFrameworkError } from "./apiErrors";
import {
  PIPELINE_JOB_POLL_MS,
  startPipelineParallelLoad,
  type PipelineParallelLoadHandlers,
  type PipelineParallelLoadDeps,
  monitorJobUntilTerminal,
} from "./pipelineParallelLoad";

/** @deprecated Use PIPELINE_JOB_POLL_MS */
export const FRAMEWORK_REVIEW_JOB_POLL_MS = PIPELINE_JOB_POLL_MS;

export interface FrameworkReviewLoadHandlers {
  onFrameworkLoaded: (framework: FrameworkVersionResponse) => void;
  onFrameworkMissing: () => void;
  onFrameworkLoadFinished: () => void;
  onFrameworkLoadError: (message: string) => void;
  onJobPollingStart: (message: string, stage: string | null, jobId: string) => void;
  onJobStageUpdate: (stage: string) => void;
  onJobPollingFinished: () => void;
  onJobFailed: PipelineParallelLoadHandlers["onJobFailed"];
  onJobSnapshot?: PipelineParallelLoadHandlers["onJobSnapshot"];
}

export interface FrameworkReviewLoadDeps {
  loadFramework: () => Promise<FrameworkVersionResponse>;
  getActiveJob: PipelineParallelLoadDeps["getActiveJob"];
  getJob: PipelineParallelLoadDeps["getJob"];
  pollIntervalMs?: number;
}

export { monitorJobUntilTerminal };

export function startFrameworkReviewParallelLoad(
  handlers: FrameworkReviewLoadHandlers,
  deps: FrameworkReviewLoadDeps,
): () => void {
  let latest: FrameworkVersionResponse | null = null;

  const mapped: PipelineParallelLoadHandlers = {
    onContentLoaded: () => {
      if (latest) {
        handlers.onFrameworkLoaded(latest);
      }
    },
    onContentMissing: handlers.onFrameworkMissing,
    onContentLoadFinished: handlers.onFrameworkLoadFinished,
    onContentLoadError: handlers.onFrameworkLoadError,
    onJobPollingStart: handlers.onJobPollingStart,
    onJobStageUpdate: handlers.onJobStageUpdate,
    onJobPollingFinished: handlers.onJobPollingFinished,
    onJobFailed: handlers.onJobFailed,
    onJobSnapshot: handlers.onJobSnapshot,
  };

  return startPipelineParallelLoad(
    "framework",
    mapped,
    {
      loadContent: async () => {
        latest = await deps.loadFramework();
      },
      isMissingError: isMissingFrameworkError,
      getActiveJob: deps.getActiveJob,
      getJob: deps.getJob,
      pollIntervalMs: deps.pollIntervalMs,
    },
  );
}
