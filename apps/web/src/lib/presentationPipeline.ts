import type { ActiveJobResponse, JobResponse } from "./api";
import type { PresentationResponse } from "./deckTypes";
import type {
  PresentationPlanGenerateResponse,
  PresentationPlanResponse,
} from "./planTypes";

export type PresentationPipelinePhase = "confirmation" | "planning" | "generation";

export type PresentationPipelineProgress =
  | { phase: "planning"; state: "waiting"; jobId: string; reused: boolean }
  | {
      phase: "planning";
      state: "completed";
      jobId: string;
      presentationPlanId: string;
    }
  | { phase: "generation"; state: "waiting"; jobId: string; reused: boolean }
  | {
      phase: "generation";
      state: "completed";
      jobId: string;
      presentationId: string;
      presentationVersionId: string;
    };

export interface PresentationPipelineResult {
  frameworkVersionId: string;
  planningJobId: string | null;
  presentationPlanId: string;
  presentationGenerationJobId: string;
  presentationId: string;
  presentationVersionId: string;
}

export type PresentationPipelineRecovery =
  | { state: "idle" }
  | { state: "completed"; result: PresentationPipelineResult };

interface ConfirmedFramework {
  id: string;
  status: string;
}

export interface PresentationPipelineApi {
  getActivePresentationJob(): Promise<ActiveJobResponse | null>;
  getJob(jobId: string): Promise<JobResponse>;
  waitForJob(jobId: string): Promise<JobResponse>;
  generatePresentationPlan(
    frameworkVersionId: string,
    autoContinue: boolean,
  ): Promise<PresentationPlanGenerateResponse>;
  getLatestPresentationPlan(): Promise<PresentationPlanResponse>;
  getPresentationPlan(presentationPlanId: string): Promise<PresentationPlanResponse>;
  getPresentation(presentationId: string): Promise<PresentationResponse>;
}

export interface PresentationPipelineOptions {
  frameworkVersionId: string;
  api: PresentationPipelineApi;
  onProgress?: (progress: PresentationPipelineProgress) => void;
}

export class PresentationPipelineError extends Error {
  readonly phase: PresentationPipelinePhase;
  readonly code?: string;
  readonly stage?: string;
  readonly retryable?: boolean;
  readonly jobId?: string;

  constructor(
    phase: PresentationPipelinePhase,
    message: string,
    details: {
      code?: string;
      stage?: string;
      retryable?: boolean;
      jobId?: string;
    } = {},
  ) {
    super(message);
    this.name = "PresentationPipelineError";
    this.phase = phase;
    this.code = details.code;
    this.stage = details.stage;
    this.retryable = details.retryable;
    this.jobId = details.jobId;
  }
}

function errorFor(
  phase: PresentationPipelinePhase,
  error: unknown,
  jobId?: string,
): PresentationPipelineError {
  if (error instanceof PresentationPipelineError) {
    return error;
  }
  const value = error && typeof error === "object" ? (error as Record<string, unknown>) : {};
  return new PresentationPipelineError(
    phase,
    error instanceof Error ? error.message : `Presentation ${phase} failed`,
    {
      code: typeof value.code === "string" ? value.code : undefined,
      stage: typeof value.stage === "string" ? value.stage : undefined,
      retryable: typeof value.retryable === "boolean" ? value.retryable : undefined,
      jobId: typeof value.jobId === "string" ? value.jobId : jobId,
    },
  );
}

function requireJobType(
  job: Pick<JobResponse, "job_id" | "job_type" | "status" | "error">,
  expectedType: "presentation_planning" | "presentation_generation",
  phase: "planning" | "generation",
): void {
  if (job.job_type !== expectedType) {
    throw new PresentationPipelineError(
      phase,
      `Expected ${expectedType} job but received ${job.job_type}`,
      { code: "PRESENTATION_PIPELINE_JOB_TYPE_MISMATCH", jobId: job.job_id },
    );
  }
  if (job.status === "FAILED") {
    throw new PresentationPipelineError(
      phase,
      job.error?.message ?? `Presentation ${phase} failed`,
      {
        code: job.error?.code,
        stage: job.error?.stage,
        retryable: job.error?.retryable,
        jobId: job.job_id,
      },
    );
  }
  if (job.status !== "COMPLETED") {
    throw new PresentationPipelineError(
      phase,
      `${expectedType} job did not reach COMPLETED`,
      { code: "PRESENTATION_PIPELINE_JOB_INCOMPLETE", jobId: job.job_id },
    );
  }
}

function resultId(job: JobResponse, key: string): string | undefined {
  const value = job.result[key];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

async function completedJob(
  api: PresentationPipelineApi,
  active: ActiveJobResponse,
  phase: "planning" | "generation",
  onProgress?: PresentationPipelineOptions["onProgress"],
): Promise<JobResponse> {
  try {
    if (active.status === "QUEUED" || active.status === "RUNNING") {
      onProgress?.({ phase, state: "waiting", jobId: active.job_id, reused: true });
      return await api.waitForJob(active.job_id);
    }
    return await api.getJob(active.job_id);
  } catch (error) {
    throw errorFor(phase, error, active.job_id);
  }
}

async function resolvePlan(
  options: PresentationPipelineOptions,
  job: JobResponse,
  expectedPlanId?: string | null,
): Promise<PresentationPlanResponse> {
  requireJobType(job, "presentation_planning", "planning");
  const jobPlanId = resultId(job, "presentation_plan_id");
  if (expectedPlanId && jobPlanId && expectedPlanId !== jobPlanId) {
    throw new PresentationPipelineError(
      "planning",
      "The completed planning job returned a different PresentationPlan identifier",
      { code: "PRESENTATION_PLAN_ID_MISMATCH", jobId: job.job_id },
    );
  }
  const persistedPlanId = jobPlanId ?? expectedPlanId ?? undefined;
  let plan: PresentationPlanResponse;
  try {
    plan = persistedPlanId
      ? await options.api.getPresentationPlan(persistedPlanId)
      : await options.api.getLatestPresentationPlan();
  } catch (error) {
    throw errorFor("planning", error, job.job_id);
  }
  if (persistedPlanId && persistedPlanId !== plan.id) {
    throw new PresentationPipelineError(
      "planning",
      "The completed planning job does not match the persisted PresentationPlan",
      { code: "PRESENTATION_PLAN_ID_MISMATCH", jobId: job.job_id },
    );
  }
  if (plan.framework_version_id !== options.frameworkVersionId) {
    throw new PresentationPipelineError(
      "planning",
      "The persisted PresentationPlan belongs to a different Framework version",
      { code: "PRESENTATION_PLAN_FRAMEWORK_MISMATCH", jobId: job.job_id },
    );
  }
  options.onProgress?.({
    phase: "planning",
    state: "completed",
    jobId: job.job_id,
    presentationPlanId: plan.id,
  });
  return plan;
}

async function resolvePresentation(
  options: PresentationPipelineOptions,
  job: JobResponse,
  plan: PresentationPlanResponse,
  expectedPresentationId?: string | null,
  expectedPlanId?: string | null,
  persistedPresentation?: PresentationResponse,
): Promise<PresentationPipelineResult> {
  requireJobType(job, "presentation_generation", "generation");
  if (plan.framework_version_id !== options.frameworkVersionId) {
    throw new PresentationPipelineError(
      "generation",
      "The presentation belongs to a different Framework version",
      { code: "PRESENTATION_FRAMEWORK_MISMATCH", jobId: job.job_id },
    );
  }
  const presentationId = resultId(job, "presentation_id") ?? expectedPresentationId ?? undefined;
  const presentationVersionId = resultId(job, "presentation_version_id");
  if (!presentationId || !presentationVersionId) {
    throw new PresentationPipelineError(
      "generation",
      "The completed presentation job is missing persisted result identifiers",
      { code: "PRESENTATION_RESULT_IDS_MISSING", jobId: job.job_id },
    );
  }
  if (expectedPresentationId && expectedPresentationId !== presentationId) {
    throw new PresentationPipelineError(
      "generation",
      "The completed job returned a different presentation identifier",
      { code: "PRESENTATION_ID_MISMATCH", jobId: job.job_id },
    );
  }
  if (expectedPlanId && expectedPlanId !== plan.id) {
    throw new PresentationPipelineError(
      "generation",
      "Presentation generation returned a different PresentationPlan identifier",
      { code: "PRESENTATION_PLAN_ID_MISMATCH", jobId: job.job_id },
    );
  }
  let presentation = persistedPresentation;
  if (!presentation) {
    try {
      presentation = await options.api.getPresentation(presentationId);
    } catch (error) {
      throw errorFor("generation", error, job.job_id);
    }
  }
  if (presentation.id !== presentationId || presentation.presentation_plan_id !== plan.id) {
    throw new PresentationPipelineError(
      "generation",
      "The completed presentation does not match the persisted PresentationPlan",
      { code: "PRESENTATION_RESULT_MISMATCH", jobId: job.job_id },
    );
  }
  options.onProgress?.({
    phase: "generation",
    state: "completed",
    jobId: job.job_id,
    presentationId,
    presentationVersionId,
  });
  return {
    frameworkVersionId: options.frameworkVersionId,
    planningJobId: null,
    presentationPlanId: plan.id,
    presentationGenerationJobId: job.job_id,
    presentationId,
    presentationVersionId,
  };
}

const HANDOFF_ATTEMPTS = 40;
const HANDOFF_INTERVAL_MS = 100;

function handoffDelay(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, HANDOFF_INTERVAL_MS));
}

async function waitForBackendGeneration(
  options: PresentationPipelineOptions,
  planningJobId: string,
  plan: PresentationPlanResponse,
): Promise<PresentationPipelineResult> {
  for (let attempt = 0; attempt < HANDOFF_ATTEMPTS; attempt += 1) {
    let active: ActiveJobResponse | null;
    try {
      active = await options.api.getActivePresentationJob();
    } catch (error) {
      throw errorFor("generation", error, planningJobId);
    }
    if (active?.job_type === "presentation_generation") {
      const recovered = await recoverActivePipeline(options, active);
      if (recovered.presentationPlanId !== plan.id) {
        throw new PresentationPipelineError(
          "generation",
          "Backend continuation used a different PresentationPlan",
          { code: "PRESENTATION_PLAN_ID_MISMATCH", jobId: recovered.presentationGenerationJobId },
        );
      }
      return { ...recovered, planningJobId };
    }
    if (
      active &&
      active.job_type !== "presentation_planning"
    ) {
      throw new PresentationPipelineError(
        "generation",
        `Unsupported presentation-stage job type: ${active.job_type}`,
        { code: "PRESENTATION_PIPELINE_JOB_TYPE_MISMATCH", jobId: active.job_id },
      );
    }
    await handoffDelay();
  }
  throw new PresentationPipelineError(
    "generation",
    "Planning completed, but backend presentation generation did not start",
    { code: "PRESENTATION_PIPELINE_HANDOFF_MISSING", jobId: planningJobId },
  );
}

async function generateNewPipeline(
  options: PresentationPipelineOptions,
): Promise<PresentationPipelineResult> {
  let generated: PresentationPlanGenerateResponse;
  try {
    generated = await options.api.generatePresentationPlan(options.frameworkVersionId, true);
  } catch (error) {
    throw errorFor("planning", error);
  }
  options.onProgress?.({
    phase: "planning",
    state: "waiting",
    jobId: generated.job_id,
    reused: Boolean(generated.is_existing_job),
  });
  let completed: JobResponse;
  try {
    completed = await options.api.waitForJob(generated.job_id);
  } catch (error) {
    throw errorFor("planning", error, generated.job_id);
  }
  const plan = await resolvePlan(options, completed, generated.presentation_plan_id);
  return waitForBackendGeneration(options, completed.job_id, plan);
}

async function recoverActivePipeline(
  options: PresentationPipelineOptions,
  active: ActiveJobResponse,
): Promise<PresentationPipelineResult> {
  if (active.job_type === "presentation_planning") {
    const current = await options.api.getJob(active.job_id);
    const enqueue = current.result._enqueue;
    if (
      !enqueue ||
      typeof enqueue !== "object" ||
      (enqueue as Record<string, unknown>).auto_continue !== true
    ) {
      throw new PresentationPipelineError(
        "planning",
        "The active planning job was started for manual Plan Preview",
        { code: "PRESENTATION_PLANNING_MANUAL", jobId: active.job_id },
      );
    }
    const completed = await completedJob(options.api, active, "planning", options.onProgress);
    const plan = await resolvePlan(options, completed);
    return waitForBackendGeneration(options, completed.job_id, plan);
  }
  if (active.job_type === "presentation_generation") {
    const completed = await completedJob(options.api, active, "generation", options.onProgress);
    requireJobType(completed, "presentation_generation", "generation");
    const presentationId = resultId(completed, "presentation_id");
    if (!presentationId) {
      throw new PresentationPipelineError(
        "generation",
        "The presentation-generation job is missing its presentation identifier",
        { code: "PRESENTATION_ID_MISSING", jobId: completed.job_id },
      );
    }
    let presentation: PresentationResponse;
    let plan: PresentationPlanResponse;
    try {
      presentation = await options.api.getPresentation(presentationId);
      plan = await options.api.getPresentationPlan(presentation.presentation_plan_id);
    } catch (error) {
      throw errorFor("generation", error, completed.job_id);
    }
    if (presentation.presentation_plan_id !== plan.id) {
      throw new PresentationPipelineError(
        "generation",
        "Recovered presentation does not match its persisted PresentationPlan",
        { code: "PRESENTATION_RESULT_MISMATCH", jobId: completed.job_id },
      );
    }
    const result = await resolvePresentation(
      options,
      completed,
      plan,
      presentationId,
      plan.id,
      presentation,
    );
    return { ...result, planningJobId: null };
  }
  throw new PresentationPipelineError(
    "generation",
    `Unsupported presentation-stage job type: ${active.job_type}`,
    { code: "PRESENTATION_PIPELINE_JOB_TYPE_MISMATCH", jobId: active.job_id },
  );
}

export async function recoverPresentationPipeline(
  options: PresentationPipelineOptions,
): Promise<PresentationPipelineRecovery> {
  let active: ActiveJobResponse | null;
  try {
    active = await options.api.getActivePresentationJob();
  } catch (error) {
    throw errorFor("generation", error);
  }
  if (!active) {
    return { state: "idle" };
  }
  if (active.job_type === "presentation_planning") {
    const job = await options.api.getJob(active.job_id);
    const enqueue = job.result._enqueue;
    if (
      !enqueue ||
      typeof enqueue !== "object" ||
      (enqueue as Record<string, unknown>).auto_continue !== true
    ) {
      return { state: "idle" };
    }
  }
  return { state: "completed", result: await recoverActivePipeline(options, active) };
}

export async function buildPresentationPipeline(
  options: PresentationPipelineOptions,
): Promise<PresentationPipelineResult> {
  let active: ActiveJobResponse | null;
  try {
    active = await options.api.getActivePresentationJob();
  } catch (error) {
    throw errorFor("generation", error);
  }
  if (active?.job_type === "presentation_generation") {
    return recoverActivePipeline(options, active);
  }
  return generateNewPipeline(options);
}

export async function approveAndBuildPresentation(options: {
  alreadyConfirmed: boolean;
  frameworkVersionId?: string;
  confirmFramework(): Promise<ConfirmedFramework>;
  api: PresentationPipelineApi;
  onProgress?: PresentationPipelineOptions["onProgress"];
}): Promise<PresentationPipelineResult> {
  let frameworkVersionId = options.frameworkVersionId;
  if (!options.alreadyConfirmed) {
    let confirmed: ConfirmedFramework;
    try {
      confirmed = await options.confirmFramework();
    } catch (error) {
      throw errorFor("confirmation", error);
    }
    if (confirmed.status.toLowerCase() !== "confirmed") {
      throw new PresentationPipelineError(
        "confirmation",
        "Framework confirmation did not return a confirmed Framework",
        { code: "FRAMEWORK_NOT_CONFIRMED" },
      );
    }
    frameworkVersionId = confirmed.id;
  }
  if (!frameworkVersionId) {
    throw new PresentationPipelineError(
      "confirmation",
      "A confirmed Framework version is required before presentation generation",
      { code: "FRAMEWORK_NOT_CONFIRMED" },
    );
  }
  return buildPresentationPipeline({
    frameworkVersionId,
    api: options.api,
    onProgress: options.onProgress,
  });
}

export function deckResultHref(
  opportunityId: string,
  result: Pick<PresentationPipelineResult, "presentationId" | "presentationVersionId">,
): string {
  const params = new URLSearchParams({
    opportunityId,
    presentationId: result.presentationId,
    presentationVersionId: result.presentationVersionId,
  });
  return `/deck-center?${params.toString()}`;
}
