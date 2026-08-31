/**
 * AT-33: Layout render stubs until remaining layout tickets replace implementations.
 *
 * Group A and Group C register real renderers on LAYOUT_REGISTRY.
 * Group B still routes through these adapters (JJ-19).
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

export type LayoutRenderFn = (
  pptx: PptxGenJS,
  spec: SlideSpecBase,
) => PptxGenJS.Slide | void;

/** Stub — executive summary layout (registered; renderer TBD). Layout: EXECUTIVE_SUMMARY_01 */
export function renderExecutiveSummary01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}

/** JJ-15 renderer adapter. Group B dispatcher registration is JJ-19. */
export function renderProcessFlow01Stub(
  pptx: PptxGenJS,
  spec: SlideSpecBase,
): PptxGenJS.Slide {
  return renderProcessFlow01(pptx, spec as ProcessFlow01SlideSpec);
}

/** JJ-16 renderer adapter. Group B dispatcher registration is JJ-19. */
export function renderTimeline01Stub(
  pptx: PptxGenJS,
  spec: SlideSpecBase,
): PptxGenJS.Slide {
  return renderTimeline01(pptx, spec as Timeline01SlideSpec);
}

/** JJ-17 renderer adapter. Group B dispatcher registration is JJ-19. */
export function renderMilestones01Stub(
  pptx: PptxGenJS,
  spec: SlideSpecBase,
): PptxGenJS.Slide {
  return renderMilestones01(pptx, spec as Milestones01SlideSpec);
}

/** JJ-18 renderer adapter. Group B dispatcher registration is JJ-19. */
export function renderTeamFte01Stub(
  pptx: PptxGenJS,
  spec: SlideSpecBase,
): PptxGenJS.Slide {
  return renderTeamFte01(pptx, spec as TeamFte01SlideSpec);
}
