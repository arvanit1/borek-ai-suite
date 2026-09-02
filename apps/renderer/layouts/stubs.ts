/**
 * AT-33: LayoutRenderFn shared by LAYOUT_REGISTRY.
 *
 * Group A, Group B, Group C, and EXECUTIVE_SUMMARY_01 register real renderers.
 */

import type PptxGenJS from "pptxgenjs";

import type { SlideSpecBase } from "../src/contracts.js";

export type LayoutRenderFn = (
  pptx: PptxGenJS,
  spec: SlideSpecBase,
) => PptxGenJS.Slide | void;
