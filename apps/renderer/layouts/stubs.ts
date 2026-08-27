/**
 * AT-33: Layout render stubs until BT/JJ/MS layout tickets replace implementations.
 *
 * One stub per registered layoutId — real renderers live in layouts/group_* when ready.
 */

import type PptxGenJS from "pptxgenjs";

import type { Cover01SlideSpec } from "../../../generated/typescript/contracts/slide_spec_group_a_cover_01.js";
import type { RequirementsMatrix01SlideSpec } from "../../../generated/typescript/contracts/slide_spec_group_a_requirements_matrix_01.js";
import type { Scope01SlideSpec } from "../../../generated/typescript/contracts/slide_spec_group_a_scope_01.js";
import type { Milestones01SlideSpec } from "../../../generated/typescript/contracts/slide_spec_group_b_milestones_01.js";
import type { ProcessFlow01SlideSpec } from "../../../generated/typescript/contracts/slide_spec_group_b_process_flow_01.js";
import type { TeamFte01SlideSpec } from "../../../generated/typescript/contracts/slide_spec_group_b_team_fte_01.js";
import type { Timeline01SlideSpec } from "../../../generated/typescript/contracts/slide_spec_group_b_timeline_01.js";
import type { SlideSpecBase } from "../src/contracts.js";
import { renderCover01 } from "./group_a/renderCover01.js";
import { renderRequirementsMatrix01 } from "./group_a/renderRequirementsMatrix01.js";
import { renderScope01 } from "./group_a/renderScope01.js";
import { renderMilestones01 } from "./group_b/renderMilestones01.js";
import { renderProcessFlow01 } from "./group_b/renderProcessFlow01.js";
import { renderTeamFte01 } from "./group_b/renderTeamFte01.js";
import { renderTimeline01 } from "./group_b/renderTimeline01.js";

export type LayoutRenderFn = (pptx: PptxGenJS, spec: SlideSpecBase) => void;

/** BT-17 renderer adapter. Full Group A dispatcher registration remains BT-22. */
export function renderCover01Stub(pptx: PptxGenJS, spec: SlideSpecBase): void {
  renderCover01(pptx, spec as Cover01SlideSpec);
}

/** Stub — executive summary layout (registered; renderer TBD). Layout: EXECUTIVE_SUMMARY_01 */
export function renderExecutiveSummary01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** Stub — BT-18 will replace this implementation. Layout: CONTEXT_01 */
export function renderContext01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** Stub — BT-19 will replace this implementation. Layout: PROBLEM_SOLUTION_01 */
export function renderProblemSolution01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** BT-20 renderer adapter. Full Group A dispatcher registration remains BT-22. */
export function renderScope01Stub(pptx: PptxGenJS, spec: SlideSpecBase): void {
  renderScope01(pptx, spec as Scope01SlideSpec);
}

/** BT-21 renderer adapter. Full Group A dispatcher registration remains BT-22. */
export function renderRequirementsMatrix01Stub(pptx: PptxGenJS, spec: SlideSpecBase): void {
  renderRequirementsMatrix01(pptx, spec as RequirementsMatrix01SlideSpec);
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
