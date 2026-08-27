/**
 * AT-33: Layout render stubs until BT/JJ/MS layout tickets replace implementations.
 *
 * One stub per registered layoutId — real renderers live in layouts/group_* when ready.
 */

import type PptxGenJS from "pptxgenjs";

import type { Milestones01SlideSpec } from "../../../generated/typescript/contracts/slide_spec_group_b_milestones_01.js";
import type { ProcessFlow01SlideSpec } from "../../../generated/typescript/contracts/slide_spec_group_b_process_flow_01.js";
import type { TeamFte01SlideSpec } from "../../../generated/typescript/contracts/slide_spec_group_b_team_fte_01.js";
import type { Timeline01SlideSpec } from "../../../generated/typescript/contracts/slide_spec_group_b_timeline_01.js";
import type { SlideSpecBase } from "../src/contracts.js";
import { renderMilestones01 } from "./group_b/renderMilestones01.js";
import { renderProcessFlow01 } from "./group_b/renderProcessFlow01.js";
import { renderTeamFte01 } from "./group_b/renderTeamFte01.js";
import { renderTimeline01 } from "./group_b/renderTimeline01.js";

export type LayoutRenderFn = (pptx: PptxGenJS, spec: SlideSpecBase) => void;

/** Stub — executive summary layout (registered; renderer TBD). Layout: EXECUTIVE_SUMMARY_01 */
export function renderExecutiveSummary01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** JJ-15 renderer adapter. Group B dispatcher registration is JJ-19. */
export function renderProcessFlow01Stub(pptx: PptxGenJS, spec: SlideSpecBase): void {
  renderProcessFlow01(pptx, spec as ProcessFlow01SlideSpec);
}

/** JJ-16 renderer adapter. Group B dispatcher registration is JJ-19. */
export function renderTimeline01Stub(pptx: PptxGenJS, spec: SlideSpecBase): void {
  renderTimeline01(pptx, spec as Timeline01SlideSpec);
}

/** JJ-17 renderer adapter. Group B dispatcher registration is JJ-19. */
export function renderMilestones01Stub(pptx: PptxGenJS, spec: SlideSpecBase): void {
  renderMilestones01(pptx, spec as Milestones01SlideSpec);
}

/** JJ-18 renderer adapter. Group B dispatcher registration is JJ-19. */
export function renderTeamFte01Stub(pptx: PptxGenJS, spec: SlideSpecBase): void {
  renderTeamFte01(pptx, spec as TeamFte01SlideSpec);
}

/** Stub — MS-16 will replace this implementation. Layout: ARCHITECTURE_01 */
export function renderArchitecture01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** Stub — MS-17 will replace this implementation. Layout: COMPLIANCE_01 */
export function renderCompliance01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** Stub — MS-18 will replace this implementation. Layout: SUCCESS_METRICS_01 */
export function renderSuccessMetrics01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** Stub — MS-19 will replace this implementation. Layout: OPEN_QUESTIONS_01 */
export function renderOpenQuestions01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** Stub — MS-20 will replace this implementation. Layout: NEXT_STEPS_01 */
export function renderNextSteps01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}
