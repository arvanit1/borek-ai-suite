import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  FRAMEWORK_PROGRESS_STAGES,
  JOB_STAGE_LABELS,
  PRESENTATION_PROGRESS_STAGES,
  SLIDE_PROGRESS_STAGES,
  buildJobProgressView,
  jobProgressPhase,
  jobProgressStages,
} from "./jobProgress.js";

/**
 * BT-27: the backend is the single source of truth for job stages and job types.
 * These checks read the production Python sources instead of restating the enum,
 * so backend drift fails the gate rather than surfacing a raw enum to a customer.
 */
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..");
const API_APP = path.join(REPO_ROOT, "apps", "services", "api", "app");

function readSource(...segments: string[]): string {
  return readFileSync(path.join(API_APP, ...segments), "utf8").replace(/\r\n/g, "\n");
}

const JOB_SCHEMAS = readSource("schemas", "jobs.py");
const WORKER = readSource("worker.py");

function backendStages(): string[] {
  const block = /class JobStage\(str, Enum\):\n((?:[ \t]+.*\n|\n)*)/.exec(JOB_SCHEMAS);
  assert.ok(block, "could not locate class JobStage in app/schemas/jobs.py");
  const stages = [...block[1].matchAll(/^\s+[A-Z0-9_]+\s*=\s*"([A-Z0-9_]+)"/gm)].map(
    (match) => match[1],
  );
  assert.ok(stages.length > 0, "parsed no JobStage members");
  return stages;
}

function backendPipelineOrder(): string[] {
  const block = /JOB_PIPELINE_STAGES[^=]*=\s*\(([^)]*)\)/.exec(JOB_SCHEMAS);
  assert.ok(block, "could not locate JOB_PIPELINE_STAGES in app/schemas/jobs.py");
  return [...block[1].matchAll(/JobStage\.([A-Z0-9_]+)/g)].map((match) => match[1]);
}

function backendJobTypes(): string[] {
  const sources = [
    readSource("services", "framework_generation.py"),
    readSource("services", "presentation_generation.py"),
  ].join("\n");
  const types = new Set(
    [...sources.matchAll(/job_type="([a-z_]+)"/g)].map((match) => match[1]),
  );
  assert.ok(types.size > 0, "parsed no backend job types");
  return [...types];
}

/** Stages a worker task really emits, in call order, duplicates collapsed. */
function workerTaskStages(taskName: string): string[] {
  const lines = WORKER.split(/\r?\n/);
  const start = lines.findIndex((line) => line.startsWith(`def ${taskName}(`));
  assert.notEqual(start, -1, `could not locate def ${taskName} in app/worker.py`);
  const rest = lines.slice(start + 1);
  const end = rest.findIndex((line) => /^(def |@)/.test(line));
  const body = (end === -1 ? rest : rest.slice(0, end)).join("\n");
  const stages: string[] = [];
  for (const match of body.matchAll(/JobStage\.([A-Z0-9_]+)/g)) {
    if (stages.at(-1) !== match[1]) {
      stages.push(match[1]);
    }
  }
  assert.ok(stages.length > 0, `${taskName} emits no JobStage`);
  return stages;
}

/**
 * Which task each job type runs. The stage values themselves are read from the
 * backend, so this map only records the flow topology.
 */
const JOB_TYPE_WORKER_TASKS: Record<string, string> = {
  framework_generation: "run_framework_generation_task",
  framework_regenerate_chapter: "run_framework_regenerate_chapter_task",
  framework_render: "run_framework_render_task",
  presentation_planning: "run_presentation_planning_task",
  presentation_generation: "run_presentation_generation_task",
  slide_regenerate: "_run_slide_task",
  slide_change_layout: "_run_slide_task",
};

function isContiguousSlice(sequence: readonly string[], candidate: readonly string[]): boolean {
  if (candidate.length === 0) {
    return false;
  }
  const start = sequence.indexOf(candidate[0]);
  if (start < 0) {
    return false;
  }
  return candidate.every((stage, offset) => sequence[start + offset] === stage);
}

const STAGES = backendStages();
const PIPELINE_ORDER = backendPipelineOrder();
const JOB_TYPES = backendJobTypes();

// 1. Every production stage has an explicit customer-facing label.
{
  for (const stage of STAGES) {
    assert.ok(
      Object.hasOwn(JOB_STAGE_LABELS, stage),
      `backend JobStage.${stage} has no customer-facing label in jobProgress.ts`,
    );
    const label = JOB_STAGE_LABELS[stage];
    assert.notEqual(label, stage, `${stage} is displayed as its raw enum value`);
    assert.doesNotMatch(label, /_/, `${stage} label "${label}" looks like a raw enum`);
    assert.ok(label.trim().length > 0, `${stage} label is blank`);
  }
}

// 2. No label describes a stage the backend no longer has.
{
  for (const stage of Object.keys(JOB_STAGE_LABELS)) {
    assert.ok(
      STAGES.includes(stage),
      `jobProgress.ts labels "${stage}", which is not a backend JobStage`,
    );
  }
}

// 3. Displayed sequences follow the backend pipeline order.
{
  for (const [name, sequence] of [
    ["FRAMEWORK_PROGRESS_STAGES", FRAMEWORK_PROGRESS_STAGES],
    ["PRESENTATION_PROGRESS_STAGES", PRESENTATION_PROGRESS_STAGES],
    ["SLIDE_PROGRESS_STAGES", SLIDE_PROGRESS_STAGES],
  ] as const) {
    assert.ok(
      isContiguousSlice(PIPELINE_ORDER, sequence),
      `${name} (${sequence.join(" → ")}) is not a contiguous slice of the backend pipeline order`,
    );
  }
}

// 4. Every job type the backend creates has a frontend progress profile.
{
  for (const jobType of JOB_TYPES) {
    assert.ok(
      jobProgressPhase(jobType),
      `backend job_type "${jobType}" has no BT-26 progress phase`,
    );
    assert.ok(
      jobProgressStages(jobType).length > 0,
      `backend job_type "${jobType}" has no BT-26 stage sequence`,
    );
  }
  for (const jobType of Object.keys(JOB_TYPE_WORKER_TASKS)) {
    assert.ok(
      JOB_TYPES.includes(jobType),
      `"${jobType}" is mapped to a worker task but the backend never creates it`,
    );
  }
}

// 5. The stages each worker really emits are exactly the ones the UI walks through.
{
  for (const [jobType, taskName] of Object.entries(JOB_TYPE_WORKER_TASKS)) {
    const emitted = workerTaskStages(taskName);
    const displayed = jobProgressStages(jobType);
    for (const stage of emitted) {
      assert.ok(STAGES.includes(stage), `${taskName} emits unknown stage ${stage}`);
      assert.ok(
        Object.hasOwn(JOB_STAGE_LABELS, stage),
        `${taskName} emits ${stage}, which has no customer-facing label`,
      );
    }
    assert.ok(
      isContiguousSlice(displayed, emitted),
      `${jobType}: worker emits ${emitted.join(" → ")} but the UI shows ${displayed.join(" → ")}`,
    );
  }
}

// 6. No stage of any job type can render a raw enum, a percentage, or an ETA.
{
  for (const jobType of JOB_TYPES) {
    for (const stage of jobProgressStages(jobType)) {
      for (const status of ["QUEUED", "RUNNING", "COMPLETED", "FAILED"] as const) {
        const view = buildJobProgressView({
          snapshot: {
            jobId: "contract-job",
            jobType,
            status,
            currentStage: stage,
            startedAt: "2026-09-02T10:00:00.000Z",
            createdAt: "2026-09-02T10:00:00.000Z",
            completedAt: null,
            error: null,
          },
        });
        assert.ok(view, `${jobType} at ${stage} produced no progress view`);
        const rendered = [view.title, view.headline, ...view.steps.map((step) => step.label)];
        for (const text of rendered) {
          assert.doesNotMatch(text, /_/, `${jobType}/${stage} renders raw enum text "${text}"`);
          assert.doesNotMatch(text, /%/, `${jobType}/${stage} renders a percentage "${text}"`);
          assert.doesNotMatch(
            text,
            /remaining|minutes left|\bETA\b/i,
            `${jobType}/${stage} renders an ETA "${text}"`,
          );
        }
      }
    }
  }
}

console.log("jobStageContract tests passed");
