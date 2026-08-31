/** AT-33 unit checks executed by pytest via `npm run test:at33 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import PptxGenJS from "pptxgenjs";
import JSZip from "jszip";

import layoutRegistryJson from "../../../packages/contracts/layout_registry.json" with { type: "json" };
import contextFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_a/context_01.minimal.json" with { type: "json" };
import coverFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_a/cover_01.minimal.json" with { type: "json" };
import problemSolutionFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_a/problem_solution_01.minimal.json" with { type: "json" };
import requirementsFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_a/requirements_matrix_01.minimal.json" with { type: "json" };
import scopeFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_a/scope_01.minimal.json" with { type: "json" };
import milestonesFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_b/milestones_01.minimal.json" with { type: "json" };
import processFlowFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_b/process_flow_01.minimal.json" with { type: "json" };
import teamFteFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_b/team_fte_01.minimal.json" with { type: "json" };
import timelineFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_b/timeline_01.minimal.json" with { type: "json" };
import architectureFixtureJson from "../../../packages/contracts/fixtures/slide_spec/architecture_01.minimal.json" with { type: "json" };
import complianceFixtureJson from "../../../packages/contracts/fixtures/slide_spec/compliance_01.minimal.json" with { type: "json" };
import nextStepsFixtureJson from "../../../packages/contracts/fixtures/slide_spec/next_steps_01.minimal.json" with { type: "json" };
import openQuestionsFixtureJson from "../../../packages/contracts/fixtures/slide_spec/open_questions_01.minimal.json" with { type: "json" };
import successMetricsFixtureJson from "../../../packages/contracts/fixtures/slide_spec/success_metrics_01.minimal.json" with { type: "json" };
import {
  MASTER_CLOSING_NAME,
  registerMasterClosing,
} from "../design_system/masters/MASTER_CLOSING.js";
import {
  MASTER_CONTENT_NAME,
  registerMasterContent,
} from "../design_system/masters/MASTER_CONTENT.js";
import {
  MASTER_COVER_NAME,
  registerMasterCover,
} from "../design_system/masters/MASTER_COVER.js";
import {
  LAYOUT_REGISTRY,
  UnsupportedLayoutError,
  dispatchSlide,
} from "./dispatcher.js";
import { renderContext01 } from "./group_a/renderContext01.js";
import { renderCover01 } from "./group_a/renderCover01.js";
import { renderProblemSolution01 } from "./group_a/renderProblemSolution01.js";
import { renderRequirementsMatrix01 } from "./group_a/renderRequirementsMatrix01.js";
import { renderScope01 } from "./group_a/renderScope01.js";
import { assertUsesMaster } from "./group_a/rendererTestHelpers.js";
import { renderMilestones01 } from "./group_b/renderMilestones01.js";
import { renderProcessFlow01 } from "./group_b/renderProcessFlow01.js";
import { renderTeamFte01 } from "./group_b/renderTeamFte01.js";
import { renderTimeline01 } from "./group_b/renderTimeline01.js";
import { renderArchitecture01 } from "./group_c/renderArchitecture01.js";
import { renderCompliance01 } from "./group_c/renderCompliance01.js";
import { renderNextSteps01 } from "./group_c/renderNextSteps01.js";
import { renderOpenQuestions01 } from "./group_c/renderOpenQuestions01.js";
import { renderSuccessMetrics01 } from "./group_c/renderSuccessMetrics01.js";
import { renderExecutiveSummary01Stub } from "./stubs.js";
import type { LayoutId, SlideSpecBase } from "../src/contracts.js";

const LAYOUTS_DIR = fileURLToPath(new URL(".", import.meta.url));
const DISPATCHER_TS = join(LAYOUTS_DIR, "dispatcher.ts");
const STUBS_TS = join(LAYOUTS_DIR, "stubs.ts");

const REGISTRY_LAYOUT_IDS = Object.keys(layoutRegistryJson.layouts).sort();
const DISPATCHER_LAYOUT_IDS = Object.keys(LAYOUT_REGISTRY).sort();

assert.ok(existsSync(DISPATCHER_TS), "dispatcher.ts must exist");
assert.ok(existsSync(STUBS_TS), "stubs.ts must exist");

assert.equal(REGISTRY_LAYOUT_IDS.length, 15, "layout_registry.json must define exactly 15 layouts");
assert.equal(DISPATCHER_LAYOUT_IDS.length, 15, "LAYOUT_REGISTRY must contain exactly 15 entries");
assert.deepEqual(
  DISPATCHER_LAYOUT_IDS,
  REGISTRY_LAYOUT_IDS,
  "LAYOUT_REGISTRY keys must match layout_registry.json layouts exactly",
);

const dispatcherSource = readFileSync(DISPATCHER_TS, "utf8");
const stubsSource = readFileSync(STUBS_TS, "utf8");
assert.doesNotMatch(
  dispatcherSource,
  /\bswitch\s*\(/,
  "dispatcher must be registry-based — no switch on layoutId in dispatcher.ts",
);
assert.doesNotMatch(
  dispatcherSource,
  /\bcase\s+"[A-Z0-9_]+"/,
  "dispatcher must be registry-based — no case branches in dispatcher.ts",
);
assert.match(
  dispatcherSource,
  /export const LAYOUT_REGISTRY/,
  "LAYOUT_REGISTRY must be the single registration point in dispatcher.ts",
);
assert.doesNotMatch(
  stubsSource,
  /render(?:Cover|Context|ProblemSolution|Scope|RequirementsMatrix)01Stub/,
  "completed Group A layouts must not retain stub renderers",
);
assert.doesNotMatch(
  stubsSource,
  /render(?:Architecture|Compliance|SuccessMetrics|OpenQuestions|NextSteps)01Stub/,
  "completed Group C layouts must not retain stub renderers",
);
assert.doesNotMatch(
  stubsSource,
  /render(?:ProcessFlow|Timeline|Milestones|TeamFte)01Stub/,
  "completed Group B layouts must not retain stub renderers",
);

const groupARenderers = {
  COVER_01: renderCover01,
  CONTEXT_01: renderContext01,
  PROBLEM_SOLUTION_01: renderProblemSolution01,
  SCOPE_01: renderScope01,
  REQUIREMENTS_MATRIX_01: renderRequirementsMatrix01,
};

const groupBRenderers = {
  PROCESS_FLOW_01: renderProcessFlow01,
  TIMELINE_01: renderTimeline01,
  MILESTONES_01: renderMilestones01,
  TEAM_FTE_01: renderTeamFte01,
};

const groupCRenderers = {
  ARCHITECTURE_01: renderArchitecture01,
  COMPLIANCE_01: renderCompliance01,
  SUCCESS_METRICS_01: renderSuccessMetrics01,
  OPEN_QUESTIONS_01: renderOpenQuestions01,
  NEXT_STEPS_01: renderNextSteps01,
};

const unchangedStubRenderers = {
  EXECUTIVE_SUMMARY_01: renderExecutiveSummary01Stub,
};

for (const [layoutId, renderer] of Object.entries(groupARenderers)) {
  assert.equal(
    LAYOUT_REGISTRY[layoutId as LayoutId],
    renderer,
    `${layoutId} must map directly to its real Group A renderer`,
  );
}

for (const [layoutId, renderer] of Object.entries(groupBRenderers)) {
  assert.equal(
    LAYOUT_REGISTRY[layoutId as LayoutId],
    renderer,
    `${layoutId} must map directly to its real Group B renderer`,
  );
}

for (const [layoutId, renderer] of Object.entries(groupCRenderers)) {
  assert.equal(
    LAYOUT_REGISTRY[layoutId as LayoutId],
    renderer,
    `${layoutId} must map directly to its real Group C renderer`,
  );
}

for (const [layoutId, renderer] of Object.entries(unchangedStubRenderers)) {
  assert.equal(
    LAYOUT_REGISTRY[layoutId as LayoutId],
    renderer,
    `${layoutId} must retain its existing Group B/C or shared stub mapping`,
  );
}

for (const name of [
  "renderProcessFlow01",
  "renderTimeline01",
  "renderMilestones01",
  "renderTeamFte01",
]) {
  assert.match(
    dispatcherSource,
    new RegExp(`from "\\./group_b/${name}\\.js"`),
    `JJ-19 must import ${name} from the Group B layout module`,
  );
}
assert.match(dispatcherSource, /PROCESS_FLOW_01: registerValidatedRenderer\(renderProcessFlow01\)/);
assert.match(dispatcherSource, /TIMELINE_01: registerValidatedRenderer\(renderTimeline01\)/);
assert.match(dispatcherSource, /MILESTONES_01: registerValidatedRenderer\(renderMilestones01\)/);
assert.match(dispatcherSource, /TEAM_FTE_01: registerValidatedRenderer\(renderTeamFte01\)/);

function minimalSlideSpec(layoutId: LayoutId): SlideSpecBase {
  const implementedSpecs: Partial<Record<LayoutId, SlideSpecBase>> = {
    COVER_01: coverFixtureJson as unknown as SlideSpecBase,
    CONTEXT_01: contextFixtureJson as unknown as SlideSpecBase,
    PROBLEM_SOLUTION_01: problemSolutionFixtureJson as unknown as SlideSpecBase,
    SCOPE_01: scopeFixtureJson as unknown as SlideSpecBase,
    REQUIREMENTS_MATRIX_01: requirementsFixtureJson as unknown as SlideSpecBase,
    PROCESS_FLOW_01: processFlowFixtureJson as unknown as SlideSpecBase,
    TIMELINE_01: timelineFixtureJson as unknown as SlideSpecBase,
    MILESTONES_01: milestonesFixtureJson as unknown as SlideSpecBase,
    TEAM_FTE_01: teamFteFixtureJson as unknown as SlideSpecBase,
    ARCHITECTURE_01: architectureFixtureJson as unknown as SlideSpecBase,
    COMPLIANCE_01: complianceFixtureJson as unknown as SlideSpecBase,
    SUCCESS_METRICS_01: successMetricsFixtureJson as unknown as SlideSpecBase,
    OPEN_QUESTIONS_01: openQuestionsFixtureJson as unknown as SlideSpecBase,
    NEXT_STEPS_01: nextStepsFixtureJson as unknown as SlideSpecBase,
  };

  if (implementedSpecs[layoutId]) {
    return implementedSpecs[layoutId];
  }

  return {
    schema_version: "1.0",
    layoutId,
    title: `Dispatch test ${layoutId}`,
    sourceChapterIds: ["1"],
  };
}

const pptx = new PptxGenJS();
registerMasterCover(pptx);
registerMasterContent(pptx);
registerMasterClosing(pptx);

for (const layoutId of REGISTRY_LAYOUT_IDS as LayoutId[]) {
  assert.doesNotThrow(
    () => dispatchSlide(pptx, minimalSlideSpec(layoutId)),
    `dispatchSlide must not throw for registered layoutId ${layoutId}`,
  );
}

const implementedMasters: Readonly<Record<string, string>> = {
  COVER_01: MASTER_COVER_NAME,
  CONTEXT_01: MASTER_CONTENT_NAME,
  PROBLEM_SOLUTION_01: MASTER_CONTENT_NAME,
  SCOPE_01: MASTER_CONTENT_NAME,
  REQUIREMENTS_MATRIX_01: MASTER_CONTENT_NAME,
  PROCESS_FLOW_01: MASTER_CONTENT_NAME,
  TIMELINE_01: MASTER_CONTENT_NAME,
  MILESTONES_01: MASTER_CONTENT_NAME,
  TEAM_FTE_01: MASTER_CONTENT_NAME,
  ARCHITECTURE_01: MASTER_CONTENT_NAME,
  COMPLIANCE_01: MASTER_CLOSING_NAME,
  SUCCESS_METRICS_01: MASTER_CONTENT_NAME,
  OPEN_QUESTIONS_01: MASTER_CONTENT_NAME,
  NEXT_STEPS_01: MASTER_CLOSING_NAME,
};

for (const [layoutId, expectedMaster] of Object.entries(implementedMasters)) {
  const spec = minimalSlideSpec(layoutId as LayoutId);
  const original = structuredClone(spec);
  const rendered = new PptxGenJS();
  registerMasterCover(rendered);
  registerMasterContent(rendered);
  registerMasterClosing(rendered);
  dispatchSlide(rendered, spec);

  assert.deepEqual(spec, original, `${layoutId} dispatch must not mutate its SlideSpec`);

  const output = await rendered.write({ outputType: "nodebuffer" });
  assert.ok(Buffer.isBuffer(output), `${layoutId} must render a PPTX buffer`);
  const zip = await JSZip.loadAsync(output);
  await assertUsesMaster(zip, expectedMaster);
}

const passThroughSpec = minimalSlideSpec("COVER_01");
const originalCoverRenderer = LAYOUT_REGISTRY.COVER_01;
let receivedSpec: SlideSpecBase | undefined;
LAYOUT_REGISTRY.COVER_01 = (_pptx, spec) => {
  receivedSpec = spec;
};
try {
  dispatchSlide(new PptxGenJS(), passThroughSpec);
} finally {
  LAYOUT_REGISTRY.COVER_01 = originalCoverRenderer;
}
assert.equal(receivedSpec, passThroughSpec, "dispatcher must pass the validated SlideSpec unchanged");

const unknownLayoutId = "UNKNOWN_LAYOUT_99";
let thrown: unknown;

try {
  dispatchSlide(pptx, {
    ...minimalSlideSpec("COVER_01"),
    layoutId: unknownLayoutId as LayoutId,
  });
} catch (error) {
  thrown = error;
}

assert.ok(thrown instanceof UnsupportedLayoutError, "unknown layoutId must throw UnsupportedLayoutError");
assert.notEqual(thrown instanceof Error && !(thrown instanceof UnsupportedLayoutError), true);
assert.equal((thrown as UnsupportedLayoutError).name, "UnsupportedLayoutError");
assert.match(
  (thrown as UnsupportedLayoutError).message,
  new RegExp(unknownLayoutId),
  "UnsupportedLayoutError message must include the layoutId",
);

process.stdout.write("AT-33 renderer unit checks passed\n");
