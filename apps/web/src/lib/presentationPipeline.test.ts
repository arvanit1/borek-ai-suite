import assert from "node:assert/strict";

import type { ActiveJobResponse, JobResponse } from "./api.js";
import type { PresentationResponse } from "./deckTypes.js";
import type { PresentationPlanResponse } from "./planTypes.js";
import {
  PresentationPipelineError,
  approveAndBuildPresentation,
  buildPresentationPipeline,
  deckResultHref,
  recoverPresentationPipeline,
} from "./presentationPipeline.js";
import type { PresentationPipelineApi } from "./presentationPipeline.js";

const FRAMEWORK_ID = "framework-version-1";
const PLAN_ID = "presentation-plan-1";
const PLANNING_JOB_ID = "planning-job-1";
const PRESENTATION_ID = "presentation-1";
const PRESENTATION_VERSION_ID = "presentation-version-1";
const GENERATION_JOB_ID = "generation-job-1";

function activeJob(
  jobType: string,
  status: ActiveJobResponse["status"] = "RUNNING",
): ActiveJobResponse {
  return {
    job_id: jobType === "presentation_planning" ? PLANNING_JOB_ID : GENERATION_JOB_ID,
    job_type: jobType,
    status,
    current_stage:
      jobType === "presentation_planning" ? "PRESENTATION_PLANNING" : "SLIDE_GENERATING",
    started_at: "2026-09-02T09:00:00Z",
    error: null,
  };
}

function completedJob(
  jobType: "presentation_planning" | "presentation_generation",
): JobResponse {
  return {
    ...activeJob(jobType, "COMPLETED"),
    current_stage: "COMPLETED",
    created_at: "2026-09-02T09:00:00Z",
    completed_at: "2026-09-02T09:01:00Z",
    result:
      jobType === "presentation_planning"
        ? {
            presentation_plan_id: PLAN_ID,
            _enqueue: { auto_continue: true },
          }
        : {
            presentation_id: PRESENTATION_ID,
            presentation_version_id: PRESENTATION_VERSION_ID,
          },
  };
}

const plan: PresentationPlanResponse = {
  id: PLAN_ID,
  framework_version_id: FRAMEWORK_ID,
  plan_json: { schema_version: "1.0", title: "Plan", slides: [] },
  created_at: "2026-09-02T09:01:00Z",
};

const presentation: PresentationResponse = {
  id: PRESENTATION_ID,
  presentation_plan_id: PLAN_ID,
  name: "Deck",
  status: "ready",
  created_at: "2026-09-02T09:02:00Z",
};

function successfulApi(
  events: string[] = [],
  overrides: Partial<PresentationPipelineApi> = {},
): PresentationPipelineApi {
  let backendGenerationAvailable = false;
  return {
    async getActivePresentationJob() {
      if (backendGenerationAvailable) {
        events.push("active:generation");
        return activeJob("presentation_generation", "COMPLETED");
      }
      events.push("active:none");
      return null;
    },
    async getJob(jobId) {
      events.push(`get-job:${jobId}`);
      return jobId === PLANNING_JOB_ID
        ? completedJob("presentation_planning")
        : completedJob("presentation_generation");
    },
    async waitForJob(jobId) {
      events.push(`wait:${jobId}`);
      if (jobId === PLANNING_JOB_ID) {
        backendGenerationAvailable = true;
        return completedJob("presentation_planning");
      }
      return completedJob("presentation_generation");
    },
    async generatePresentationPlan(frameworkVersionId, autoContinue) {
      events.push(`plan:${frameworkVersionId}`);
      assert.equal(autoContinue, true);
      return {
        job_id: PLANNING_JOB_ID,
        status: "queued",
        presentation_plan_id: PLAN_ID,
        is_existing_job: false,
      };
    },
    async getLatestPresentationPlan() {
      events.push("get-latest-plan");
      return plan;
    },
    async getPresentationPlan(presentationPlanId) {
      events.push(`get-plan:${presentationPlanId}`);
      return plan;
    },
    async getPresentation(presentationId) {
      events.push(`get-presentation:${presentationId}`);
      return presentation;
    },
    ...overrides,
  };
}

async function main() {
{
  const events: string[] = [];
  const result = await approveAndBuildPresentation({
    alreadyConfirmed: false,
    confirmFramework: async () => {
      events.push("confirm");
      return { id: FRAMEWORK_ID, status: "confirmed" };
    },
    api: successfulApi(events),
  });
  assert.deepEqual(events, [
    "confirm",
    "active:none",
    `plan:${FRAMEWORK_ID}`,
    `wait:${PLANNING_JOB_ID}`,
    `get-plan:${PLAN_ID}`,
    "active:generation",
    `get-job:${GENERATION_JOB_ID}`,
    `get-presentation:${PRESENTATION_ID}`,
    `get-plan:${PLAN_ID}`,
  ]);
  assert.deepEqual(result, {
    frameworkVersionId: FRAMEWORK_ID,
    planningJobId: PLANNING_JOB_ID,
    presentationPlanId: PLAN_ID,
    presentationGenerationJobId: GENERATION_JOB_ID,
    presentationId: PRESENTATION_ID,
    presentationVersionId: PRESENTATION_VERSION_ID,
  });
}

{
  let planningStarted = false;
  await assert.rejects(
    approveAndBuildPresentation({
      alreadyConfirmed: false,
      confirmFramework: async () => {
        throw new Error("Confirmation rejected");
      },
      api: successfulApi([], {
        async generatePresentationPlan() {
          planningStarted = true;
          throw new Error("must not run");
        },
      }),
    }),
    (error: unknown) =>
      error instanceof PresentationPipelineError && error.phase === "confirmation",
  );
  assert.equal(planningStarted, false, "planning must not start before human confirmation succeeds");
}

{
  let confirmCalls = 0;
  await approveAndBuildPresentation({
    alreadyConfirmed: true,
    frameworkVersionId: FRAMEWORK_ID,
    confirmFramework: async () => {
      confirmCalls += 1;
      throw new Error("already-confirmed Framework must not be confirmed again");
    },
    api: successfulApi(),
  });
  assert.equal(confirmCalls, 0);
}

{
  let releasePlanning!: (job: JobResponse) => void;
  const planningCompletion = new Promise<JobResponse>((resolve) => {
    releasePlanning = resolve;
  });
  let generationRecoveryCalls = 0;
  let planningComplete = false;
  const running = buildPresentationPipeline({
    frameworkVersionId: FRAMEWORK_ID,
    api: successfulApi([], {
      async getActivePresentationJob() {
        if (!planningComplete) {
          return null;
        }
        generationRecoveryCalls += 1;
        return activeJob("presentation_generation", "COMPLETED");
      },
      async waitForJob(jobId) {
        if (jobId === PLANNING_JOB_ID) {
          const completed = await planningCompletion;
          planningComplete = true;
          return completed;
        }
        return completedJob("presentation_generation");
      },
    }),
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(
    generationRecoveryCalls,
    0,
    "generation must not be observed before planning COMPLETED",
  );
  releasePlanning(completedJob("presentation_planning"));
  await running;
  assert.equal(generationRecoveryCalls, 1);
}

{
  const progress: unknown[] = [];
  let activeCalls = 0;
  const result = await buildPresentationPipeline({
    frameworkVersionId: FRAMEWORK_ID,
    api: successfulApi([], {
      async getActivePresentationJob() {
        activeCalls += 1;
        return activeCalls === 1 ? null : activeJob("presentation_generation");
      },
      async generatePresentationPlan() {
        return {
          job_id: PLANNING_JOB_ID,
          status: "running",
          presentation_plan_id: PLAN_ID,
          is_existing_job: true,
        };
      },
    }),
    onProgress: (event) => progress.push(event),
  });
  assert.equal(result.planningJobId, PLANNING_JOB_ID);
  assert.deepEqual(
    progress.filter(
      (event) =>
        typeof event === "object" &&
        event !== null &&
        "state" in event &&
        event.state === "waiting",
    ),
    [
      { phase: "planning", state: "waiting", jobId: PLANNING_JOB_ID, reused: true },
      { phase: "generation", state: "waiting", jobId: GENERATION_JOB_ID, reused: true },
    ],
  );
}

{
  const events: string[] = [];
  let activeCalls = 0;
  const recovery = await recoverPresentationPipeline({
    frameworkVersionId: FRAMEWORK_ID,
    api: successfulApi(events, {
      async getActivePresentationJob() {
        activeCalls += 1;
        events.push(activeCalls === 1 ? "active:planning" : "active:generation");
        return activeCalls === 1
          ? activeJob("presentation_planning")
          : activeJob("presentation_generation", "COMPLETED");
      },
      async generatePresentationPlan() {
        throw new Error("refresh must not POST plan generation");
      },
    }),
  });
  assert.equal(recovery.state, "completed");
  assert.equal(events.includes(`wait:${PLANNING_JOB_ID}`), true);
  assert.equal(events.includes("active:generation"), true);
}

{
  const events: string[] = [];
  const recovery = await recoverPresentationPipeline({
    frameworkVersionId: FRAMEWORK_ID,
    api: successfulApi(events, {
      async getActivePresentationJob() {
        events.push("active:generation");
        return activeJob("presentation_generation");
      },
      async generatePresentationPlan() {
        throw new Error("refresh must not POST plan generation");
      },
    }),
  });
  assert.equal(recovery.state, "completed");
  if (recovery.state === "completed") {
    assert.equal(recovery.result.presentationId, PRESENTATION_ID);
    assert.equal(recovery.result.presentationVersionId, PRESENTATION_VERSION_ID);
    assert.equal(recovery.result.planningJobId, null);
  }
  assert.equal(events.includes(`wait:${GENERATION_JOB_ID}`), true);
  assert.equal(events.includes(`get-plan:${PLAN_ID}`), true);
}

{
  let activeCalls = 0;
  await assert.rejects(
    buildPresentationPipeline({
      frameworkVersionId: FRAMEWORK_ID,
      api: successfulApi([], {
        async getActivePresentationJob() {
          activeCalls += 1;
          return null;
        },
        async waitForJob(jobId) {
          if (jobId === PLANNING_JOB_ID) {
            throw Object.assign(new Error("Planning failed"), {
              code: "PRESENTATION_PLANNING_FAILED",
              jobId,
            });
          }
          return completedJob("presentation_generation");
        },
      }),
    }),
    (error: unknown) =>
      error instanceof PresentationPipelineError &&
      error.phase === "planning" &&
      error.jobId === PLANNING_JOB_ID,
  );
  assert.equal(activeCalls, 1, "planning failure must stop before generation recovery");
}

{
  let planningCalls = 0;
  let activeCalls = 0;
  await assert.rejects(
    approveAndBuildPresentation({
      alreadyConfirmed: true,
      frameworkVersionId: FRAMEWORK_ID,
      confirmFramework: async () => {
        throw new Error("must not reconfirm");
      },
      api: successfulApi([], {
        async getActivePresentationJob() {
          activeCalls += 1;
          return activeCalls === 1 ? null : activeJob("presentation_generation");
        },
        async generatePresentationPlan(frameworkVersionId, autoContinue) {
          planningCalls += 1;
          assert.equal(autoContinue, true);
          return {
            job_id: PLANNING_JOB_ID,
            status: "queued",
            presentation_plan_id: PLAN_ID,
            is_existing_job: false,
          };
        },
        async waitForJob(jobId) {
          if (jobId === GENERATION_JOB_ID) {
            throw Object.assign(new Error("Rendering failed"), {
              code: "RENDER_FAILED",
              jobId,
            });
          }
          return completedJob("presentation_planning");
        },
      }),
    }),
    (error: unknown) =>
      error instanceof PresentationPipelineError &&
      error.phase === "generation" &&
      error.jobId === GENERATION_JOB_ID,
  );
  assert.equal(planningCalls, 1, "generation failure must not restart Framework or planning work");
}

{
  let jobReads = 0;
  const recovery = await recoverPresentationPipeline({
    frameworkVersionId: FRAMEWORK_ID,
    api: successfulApi([], {
      async getActivePresentationJob() {
        return activeJob("presentation_planning");
      },
      async getJob(jobId) {
        jobReads += 1;
        const job = completedJob("presentation_planning");
        job.job_id = jobId;
        job.result._enqueue = { auto_continue: false };
        return job;
      },
    }),
  });
  assert.deepEqual(recovery, { state: "idle" });
  assert.equal(jobReads, 1, "manual Plan Preview jobs remain recoverable only by the manual flow");
}

{
  const recovery = await recoverPresentationPipeline({
    frameworkVersionId: FRAMEWORK_ID,
    api: successfulApi(),
  });
  assert.deepEqual(recovery, { state: "idle" });
}

{
  let planningCalls = 0;
  const result = await buildPresentationPipeline({
    frameworkVersionId: FRAMEWORK_ID,
    api: successfulApi([], {
      async getActivePresentationJob() {
        return activeJob("presentation_generation");
      },
      async generatePresentationPlan() {
        planningCalls += 1;
        throw new Error("active generation must not start planning");
      },
    }),
  });
  assert.equal(planningCalls, 0);
  assert.equal(result.presentationGenerationJobId, GENERATION_JOB_ID);
  assert.equal(result.presentationId, PRESENTATION_ID);
}

assert.equal(
  deckResultHref("opportunity-1", {
    presentationId: PRESENTATION_ID,
    presentationVersionId: PRESENTATION_VERSION_ID,
  }),
  "/deck-center?opportunityId=opportunity-1&presentationId=presentation-1&presentationVersionId=presentation-version-1",
);

console.log("BT-25 presentation pipeline tests passed");
}

void main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
