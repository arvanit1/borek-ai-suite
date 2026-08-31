/**
 * AT-33: Layout render stubs until remaining layout tickets replace implementations.
 *
 * Group A, Group B, and Group C register real renderers on LAYOUT_REGISTRY.
 */

import type PptxGenJS from "pptxgenjs";

import type { SlideSpecBase } from "../src/contracts.js";

export type LayoutRenderFn = (pptx: PptxGenJS, spec: SlideSpecBase) => void;

/** Stub — executive summary layout (registered; renderer TBD). Layout: EXECUTIVE_SUMMARY_01 */
export function renderExecutiveSummary01Stub(_pptx: PptxGenJS, _spec: SlideSpecBase): void {
  // Intentionally empty — dispatcher routing test only.
}
