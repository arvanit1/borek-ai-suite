/**
 * AT-13: Borek spacing tokens (technical plan v2 §16 — BorekTheme.spacing).
 *
 * Single source for margins and footer height in the renderer.
 * Grid gaps live in grid.ts. Layout and component code must import by token name.
 *
 * All values are in inches (PptxGenJS positioning convention).
 */

export const BorekSpacing = {
  marginX: 0.65,
  marginTop: 0.5,
  footerHeight: 0.35,
} as const;

export type BorekSpacingToken = keyof typeof BorekSpacing;

export type BorekSpacingInches = (typeof BorekSpacing)[BorekSpacingToken];

export const BorekSpacingTokens = {
  spacing: BorekSpacing,
} as const;

/** All spacing tokens as a plain record (for tests and future theme wiring). */
export const BOREK_SPACING_TOKENS = BorekSpacingTokens;
