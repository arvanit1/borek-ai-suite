/**
 * Borek grid spacing tokens (technical plan v2 §16 — design-system/grid.ts).
 *
 * Column and row gaps for multi-column layouts. Values derive from BorekSpacing —
 * never hardcode gap literals in layouts or components.
 *
 * All values are in inches (PptxGenJS positioning convention).
 */

import { BorekSpacing } from "./spacing.js";

export const BorekGrid = {
  columnGap: BorekSpacing.marginX / 2,
  rowGap: BorekSpacing.marginTop / 2,
} as const;

export type BorekGridToken = keyof typeof BorekGrid;

export type BorekGridInches = (typeof BorekGrid)[BorekGridToken];

export const BorekGridTokens = {
  grid: BorekGrid,
} as const;

/** All grid tokens as a plain record (for tests and future theme wiring). */
export const BOREK_GRID_TOKENS = BorekGridTokens;
