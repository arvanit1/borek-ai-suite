/**
 * AT-33: Renderer layout dispatcher (technical plan v2 §17.3).
 *
 * Single registry routes SlideSpec.layoutId to a layout render function.
 * No rendering logic or design-system imports — only stub/real layout modules.
 */

import type PptxGenJS from "pptxgenjs";

import type { LayoutId, SlideSpecBase } from "../src/contracts.js";
import { renderContext01 } from "./group_a/renderContext01.js";
import { renderCover01 } from "./group_a/renderCover01.js";
import { renderProblemSolution01 } from "./group_a/renderProblemSolution01.js";
import { renderRequirementsMatrix01 } from "./group_a/renderRequirementsMatrix01.js";
import { renderScope01 } from "./group_a/renderScope01.js";
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
  type LayoutRenderFn,
} from "./stubs.js";

export type RenderFn = LayoutRenderFn;

type ValidatedLayoutRenderFn<TSpec extends SlideSpecBase> = (
  pptx: PptxGenJS,
  spec: Readonly<TSpec>,
) => unknown;

/** Register a layout-specific renderer after upstream validation has matched its layoutId. */
function registerValidatedRenderer<TSpec extends SlideSpecBase>(
  render: ValidatedLayoutRenderFn<TSpec>,
): RenderFn {
  return render as unknown as RenderFn;
}

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
  COVER_01: registerValidatedRenderer(renderCover01),
  EXECUTIVE_SUMMARY_01: renderExecutiveSummary01Stub,
  CONTEXT_01: registerValidatedRenderer(renderContext01),
  PROBLEM_SOLUTION_01: registerValidatedRenderer(renderProblemSolution01),
  SCOPE_01: registerValidatedRenderer(renderScope01),
  REQUIREMENTS_MATRIX_01: registerValidatedRenderer(renderRequirementsMatrix01),
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
