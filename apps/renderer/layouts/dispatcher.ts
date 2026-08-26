/**
 * AT-33: Renderer layout dispatcher (technical plan v2 §17.3).
 *
 * Single registry routes SlideSpec.layoutId to a layout render function.
 * No rendering logic or design-system imports — only stub/real layout modules.
 */

import type PptxGenJS from "pptxgenjs";

import type { LayoutId, SlideSpecBase } from "../src/contracts.js";
import {
  renderArchitecture01Stub,
  renderCompliance01Stub,
  renderContext01Stub,
  renderCover01Stub,
  renderExecutiveSummary01Stub,
  renderMilestones01Stub,
  renderNextSteps01Stub,
  renderOpenQuestions01Stub,
  renderProblemSolution01Stub,
  renderProcessFlow01Stub,
  renderRequirementsMatrix01Stub,
  renderScope01Stub,
  renderSuccessMetrics01Stub,
  renderTeamFte01Stub,
  renderTimeline01Stub,
  type LayoutRenderFn,
} from "./stubs.js";

export type RenderFn = LayoutRenderFn;

/** Thrown when slide.layoutId is not registered in LAYOUT_REGISTRY. */
export class UnsupportedLayoutError extends Error {
  constructor(layoutId: string) {
    super(`No render function registered for layoutId: ${layoutId}`);
    this.name = "UnsupportedLayoutError";
  }
}

/**
 * Canonical layoutId → render function map (technical plan v2 §17.3).
 * BT/JJ/MS tickets replace stub values — do not add per-layout switches elsewhere.
 */
export const LAYOUT_REGISTRY: Record<LayoutId, RenderFn> = {
  COVER_01: renderCover01Stub,
  EXECUTIVE_SUMMARY_01: renderExecutiveSummary01Stub,
  CONTEXT_01: renderContext01Stub,
  PROBLEM_SOLUTION_01: renderProblemSolution01Stub,
  SCOPE_01: renderScope01Stub,
  REQUIREMENTS_MATRIX_01: renderRequirementsMatrix01Stub,
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

/**
 * Route a SlideSpec to its layout render function by layoutId.
 *
 * @example
 * dispatchSlide(pptx, slideSpec);
 */
export function dispatchSlide(pptx: PptxGenJS, spec: SlideSpecBase): void {
  const render = LAYOUT_REGISTRY[spec.layoutId];

  if (!render) {
    throw new UnsupportedLayoutError(spec.layoutId);
  }

  render(pptx, spec);
}
