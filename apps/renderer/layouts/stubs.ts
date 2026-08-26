/**
 * AT-33: Layout render stubs until BT/JJ/MS layout tickets replace implementations.
 *
 * One stub per registered layoutId — real renderers live in layouts/group_* when ready.
 */

import type PptxGenJS from "pptxgenjs";

import type { SlideSpecBase } from "../src/contracts.js";

export type LayoutRenderFn = (pptx: PptxGenJS, spec: SlideSpecBase) => void;

/** Stub — BT-17 will replace this implementation. Layout: COVER_01 */
export function renderCover01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
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

/** Stub — BT-20 will replace this implementation. Layout: SCOPE_01 */
export function renderScope01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** Stub — BT-21 will replace this implementation. Layout: REQUIREMENTS_MATRIX_01 */
export function renderRequirementsMatrix01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** Stub — JJ-15 will replace this implementation. Layout: PROCESS_FLOW_01 */
export function renderProcessFlow01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** Stub — JJ-16 will replace this implementation. Layout: TIMELINE_01 */
export function renderTimeline01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** Stub — JJ-17 will replace this implementation. Layout: MILESTONES_01 */
export function renderMilestones01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** Stub — JJ-18 will replace this implementation. Layout: TEAM_FTE_01 */
export function renderTeamFte01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
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
