import type { ActiveJobResponse, JobErrorDetail, JobResponse } from "./api";

export type JobProgressPhase = "framework" | "planning" | "generation" | "slide";
export type JobProgressStepState = "complete" | "current" | "upcoming" | "failed";
export type JobProgressStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";

/** Real backend stages (app.schemas.jobs.JobStage) mapped to customer-facing copy. */
export const JOB_STAGE_LABELS: Record<string, string> = {
  QUEUED: "Waiting to start",
  TRANSCRIPT_PROCESSING: "Processing customer context",
  KNOWLEDGE_EXTRACTING: "Reading transcripts",
  FRAMEWORK_SYNTHESIZING: "Building Framework",
  FRAMEWORK_VALIDATING: "Checking Framework",
  PRESENTATION_PLANNING: "Preparing presentation structure",
  SLIDE_GENERATING: "Generating slide content",
  SLIDE_VALIDATING: "Validating slides",
  PPTX_RENDERING: "Rendering PowerPoint/PDF",
  PREVIEW_RENDERING: "Preparing preview",
  COMPLETED: "Finished",
  FAILED: "Stopped",
};

export const FRAMEWORK_PROGRESS_STAGES = [
  "TRANSCRIPT_PROCESSING",
  "KNOWLEDGE_EXTRACTING",
  "FRAMEWORK_SYNTHESIZING",
  "FRAMEWORK_VALIDATING",
] as const;

export const PRESENTATION_PROGRESS_STAGES = [
  "PRESENTATION_PLANNING",
  "SLIDE_GENERATING",
  "SLIDE_VALIDATING",
  "PPTX_RENDERING",
  "PREVIEW_RENDERING",
] as const;

export const SLIDE_PROGRESS_STAGES = [
  "SLIDE_GENERATING",
  "SLIDE_VALIDATING",
  "PPTX_RENDERING",
  "PREVIEW_RENDERING",
] as const;

interface JobTypeProfile {
  phase: JobProgressPhase;
  stages: readonly string[];
  startStage: string;
  title: string;
  completedHeadline: string;
  /** True when reaching COMPLETED means the whole displayed sequence is done. */
  completesSequence: boolean;
}

const JOB_TYPE_PROFILES: Record<string, JobTypeProfile> = {
  framework_generation: {
    phase: "framework",
    stages: FRAMEWORK_PROGRESS_STAGES,
    startStage: "TRANSCRIPT_PROCESSING",
    title: "Building your customer story",
    completedHeadline: "Customer story ready",
    completesSequence: true,
  },
  framework_regenerate_chapter: {
    phase: "framework",
    stages: FRAMEWORK_PROGRESS_STAGES,
    startStage: "TRANSCRIPT_PROCESSING",
    title: "Updating the chapter",
    completedHeadline: "Chapter updated",
    completesSequence: true,
  },
  framework_render: {
    phase: "framework",
    stages: ["PREVIEW_RENDERING"],
    startStage: "PREVIEW_RENDERING",
    title: "Preparing your framework download",
    completedHeadline: "Framework download ready",
    completesSequence: true,
  },
  presentation_planning: {
    phase: "planning",
    stages: PRESENTATION_PROGRESS_STAGES,
    startStage: "PRESENTATION_PLANNING",
    title: "Building your presentation",
    completedHeadline: "Presentation structure prepared",
    completesSequence: false,
  },
  presentation_generation: {
    phase: "generation",
    stages: PRESENTATION_PROGRESS_STAGES,
    startStage: "SLIDE_GENERATING",
    title: "Building your presentation",
    completedHeadline: "Presentation ready",
    completesSequence: true,
  },
  slide_regenerate: {
    phase: "slide",
    stages: SLIDE_PROGRESS_STAGES,
    startStage: "SLIDE_GENERATING",
    title: "Updating the slide",
    completedHeadline: "Slide updated",
    completesSequence: true,
  },
  slide_change_layout: {
    phase: "slide",
    stages: SLIDE_PROGRESS_STAGES,
    startStage: "SLIDE_GENERATING",
    title: "Updating the slide layout",
    completedHeadline: "Slide layout updated",
    completesSequence: true,
  },
};

export interface JobProgressSnapshot {
  jobId: string;
  jobType: string;
  status: JobProgressStatus;
  currentStage: string;
  startedAt: string | null;
  createdAt: string | null;
  completedAt: string | null;
  error: JobErrorDetail | null;
}

export interface JobProgressStep {
  id: string;
  label: string;
  state: JobProgressStepState;
}

export interface JobProgressView {
  jobId: string;
  jobType: string;
  phase: JobProgressPhase;
  status: JobProgressStatus;
  title: string;
  headline: string;
  steps: JobProgressStep[];
  /** ISO timestamp the elapsed counter runs from — never a prediction. */
  elapsedFrom: string | null;
  elapsedTo: string | null;
  detail: string | null;
  failed: boolean;
  error: JobErrorDetail | null;
}

export interface JobProgressInput {
  snapshot: JobProgressSnapshot | null;
  /**
   * Planning finished and BT-25 backend continuation has not surfaced the
   * generation job yet. A legitimate waiting state, never an error.
   */
  handoff?: boolean;
  /** Only from a persisted PresentationPlan — never inferred while generating. */
  plannedSlideCount?: number | null;
}

function humanizeStage(stage: string): string {
  const words = stage.replaceAll("_", " ").trim().toLowerCase();
  if (!words) {
    return "Working";
  }
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function jobStageLabel(stage: string | null | undefined): string {
  if (!stage) {
    return JOB_STAGE_LABELS.QUEUED;
  }
  return JOB_STAGE_LABELS[stage] ?? humanizeStage(stage);
}

export function jobProgressPhase(jobType: string): JobProgressPhase | null {
  return JOB_TYPE_PROFILES[jobType]?.phase ?? null;
}

export function jobProgressStages(jobType: string): readonly string[] {
  return JOB_TYPE_PROFILES[jobType]?.stages ?? [];
}

export function snapshotFromJob(job: JobResponse): JobProgressSnapshot {
  return {
    jobId: job.job_id,
    jobType: job.job_type,
    status: job.status,
    currentStage: job.current_stage,
    startedAt: job.started_at,
    createdAt: job.created_at,
    completedAt: job.completed_at,
    error: job.error,
  };
}

export function snapshotFromActiveJob(job: ActiveJobResponse): JobProgressSnapshot {
  return {
    jobId: job.job_id,
    jobType: job.job_type,
    status: job.status,
    currentStage: job.current_stage,
    startedAt: job.started_at,
    createdAt: null,
    completedAt: null,
    error: job.error,
  };
}

export function elapsedMsSince(
  snapshot: Pick<JobProgressSnapshot, "startedAt" | "createdAt" | "completedAt">,
  nowMs: number,
): number | null {
  const from = snapshot.startedAt ?? snapshot.createdAt;
  if (!from) {
    return null;
  }
  const started = Date.parse(from);
  if (Number.isNaN(started)) {
    return null;
  }
  const end = snapshot.completedAt ? Date.parse(snapshot.completedAt) : nowMs;
  return Math.max(0, (Number.isNaN(end) ? nowMs : end) - started);
}

export function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const seconds = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  const minutes = totalMinutes % 60;
  const hours = Math.floor(totalMinutes / 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (totalMinutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

export function formatElapsedLabel(ms: number): string {
  return `Elapsed ${formatElapsed(ms)}`;
}

function stageIndex(stages: readonly string[], stage: string | null | undefined): number {
  return stage ? stages.indexOf(stage) : -1;
}

function stepsFor(
  stages: readonly string[],
  states: JobProgressStepState[],
): JobProgressStep[] {
  return stages.map((stage, index) => ({
    id: stage,
    label: jobStageLabel(stage),
    state: states[index],
  }));
}

export function buildJobProgressView(input: JobProgressInput): JobProgressView | null {
  const snapshot = input.snapshot;
  if (!snapshot) {
    return null;
  }
  const profile = JOB_TYPE_PROFILES[snapshot.jobType];
  if (!profile) {
    return null;
  }

  const stages = profile.stages;
  const states: JobProgressStepState[] = stages.map(() => "upcoming");
  const startIndex = Math.max(0, stageIndex(stages, profile.startStage));
  // A generation job can only exist once planning persisted its plan.
  for (let index = 0; index < startIndex; index += 1) {
    states[index] = "complete";
  }

  let headline = jobStageLabel(snapshot.currentStage);
  let failed = false;

  if (snapshot.status === "FAILED") {
    failed = true;
    const failedIndex = Math.max(
      startIndex,
      stageIndex(stages, snapshot.error?.stage ?? snapshot.currentStage),
    );
    for (let index = 0; index < failedIndex; index += 1) {
      states[index] = "complete";
    }
    if (failedIndex < states.length) {
      states[failedIndex] = "failed";
    }
    headline =
      snapshot.error?.message ??
      `Stopped at ${jobStageLabel(snapshot.error?.stage ?? snapshot.currentStage)}`;
  } else if (snapshot.status === "COMPLETED") {
    const reached = profile.completesSequence ? states.length : startIndex + 1;
    for (let index = 0; index < reached; index += 1) {
      states[index] = "complete";
    }
    headline = input.handoff ? "Starting presentation generation" : profile.completedHeadline;
  } else if (snapshot.status === "QUEUED") {
    headline = JOB_STAGE_LABELS.QUEUED;
  } else {
    const currentIndex = stageIndex(stages, snapshot.currentStage);
    const activeIndex = currentIndex >= 0 ? Math.max(currentIndex, startIndex) : startIndex;
    for (let index = 0; index < activeIndex; index += 1) {
      states[index] = "complete";
    }
    states[activeIndex] = "current";
    headline = jobStageLabel(currentIndex >= 0 ? snapshot.currentStage : profile.startStage);
  }

  const plannedSlides = input.plannedSlideCount ?? null;
  const detail =
    plannedSlides && plannedSlides > 0
      ? `${plannedSlides} slide${plannedSlides === 1 ? "" : "s"} planned`
      : null;

  return {
    jobId: snapshot.jobId,
    jobType: snapshot.jobType,
    phase: profile.phase,
    status: snapshot.status,
    title: profile.title,
    headline,
    steps: stepsFor(stages, states),
    elapsedFrom: snapshot.startedAt ?? snapshot.createdAt,
    elapsedTo: snapshot.completedAt,
    detail,
    failed,
    error: snapshot.error,
  };
}
