/**
 * Borek spacing tokens (Brand Guide 2.0 — 120px margins at 1920×1080).
 *
 * Single source for margins and footer height in the renderer.
 * Grid gaps live in grid.ts. Layout and component code must import by token name.
 *
 * All values are in inches (PptxGenJS positioning convention).
 * 120px at 144dpi design grid = 120/144 ≈ 0.833in.
 */

/** 120px margin converted to inches on the 13.333×7.5in (1920×1080) slide grid. */
const CI_MARGIN_INCHES = 120 / 144;

export const BorekSpacing = {
  marginX: CI_MARGIN_INCHES,
  marginTop: CI_MARGIN_INCHES,
  footerHeight: 0.35,
} as const;

export type BorekSpacingToken = keyof typeof BorekSpacing;

export type BorekSpacingInches = (typeof BorekSpacing)[BorekSpacingToken];

export const BorekSpacingTokens = {
  spacing: BorekSpacing,
} as const;

/** All spacing tokens as a plain record (for tests and future theme wiring). */
export const BOREK_SPACING_TOKENS = BorekSpacingTokens;
