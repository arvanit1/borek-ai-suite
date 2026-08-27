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
import {
  renderArchitecture01Stub,
  renderCompliance01Stub,
  renderExecutiveSummary01Stub,
  renderMilestones01Stub,
  renderNextSteps01Stub,
  renderOpenQuestions01Stub,
  renderProcessFlow01Stub,
  renderSuccessMetrics01Stub,
  renderTeamFte01Stub,
  renderTimeline01Stub,
} from "./stubs.js";
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

const groupARenderers = {
  COVER_01: renderCover01,
  CONTEXT_01: renderContext01,
  PROBLEM_SOLUTION_01: renderProblemSolution01,
  SCOPE_01: renderScope01,
  REQUIREMENTS_MATRIX_01: renderRequirementsMatrix01,
};

const unchangedStubRenderers = {
  EXECUTIVE_SUMMARY_01: renderExecutiveSummary01Stub,
  PROCESS_FLOW_01: renderProcessFlow01Stub,
  TIMELINE_01: renderTimeline01Stub,
  MILESTONES_01: renderMilestones01Stub,
  TEAM_FTE_01: renderTeamFte01Stub,
  ARCHITECTURE_01: renderArchitecture01Stub,
  COMPLIANCE_01: renderCompliance01Stub,
  SUCCESS_METRICS_01: renderSuccessMetrics01Stub,
  OPEN_QUESTIONS_01: renderOpenQuestions01Stub,
  NEXT_STEPS_01: renderNextSteps01Stub,
};

for (const [layoutId, renderer] of Object.entries(groupARenderers)) {
  assert.equal(
    LAYOUT_REGISTRY[layoutId as LayoutId],
    renderer,
    `${layoutId} must map directly to its real Group A renderer`,
  );
}

for (const [layoutId, renderer] of Object.entries(unchangedStubRenderers)) {
  assert.equal(
    LAYOUT_REGISTRY[layoutId as LayoutId],
    renderer,
    `${layoutId} must retain its existing Group B/C or shared stub mapping`,
  );
}

function minimalSlideSpec(layoutId: LayoutId): SlideSpecBase {
  const implementedGroupASpecs: Partial<Record<LayoutId, SlideSpecBase>> = {
    COVER_01: coverFixtureJson as unknown as SlideSpecBase,
    CONTEXT_01: contextFixtureJson as unknown as SlideSpecBase,
    PROBLEM_SOLUTION_01: problemSolutionFixtureJson as unknown as SlideSpecBase,
    SCOPE_01: scopeFixtureJson as unknown as SlideSpecBase,
    REQUIREMENTS_MATRIX_01: requirementsFixtureJson as unknown as SlideSpecBase,
  };

  if (implementedGroupASpecs[layoutId]) {
    return implementedGroupASpecs[layoutId];
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

for (const layoutId of REGISTRY_LAYOUT_IDS as LayoutId[]) {
  assert.doesNotThrow(
    () => dispatchSlide(pptx, minimalSlideSpec(layoutId)),
    `dispatchSlide must not throw for registered layoutId ${layoutId}`,
  );
}

const groupAMasters: Readonly<Record<string, string>> = {
  COVER_01: MASTER_COVER_NAME,
  CONTEXT_01: MASTER_CONTENT_NAME,
  PROBLEM_SOLUTION_01: MASTER_CONTENT_NAME,
  SCOPE_01: MASTER_CONTENT_NAME,
  REQUIREMENTS_MATRIX_01: MASTER_CONTENT_NAME,
};

for (const [layoutId, expectedMaster] of Object.entries(groupAMasters)) {
  const spec = minimalSlideSpec(layoutId as LayoutId);
  const original = structuredClone(spec);
  const rendered = new PptxGenJS();
  registerMasterCover(rendered);
  registerMasterContent(rendered);
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
