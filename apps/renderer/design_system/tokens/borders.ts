/**
 * Borek border tokens (technical plan v2 §16 — design-system/borders.ts).
 *
 * Shared border radius and line weights for cards and dividers.
 * Colors reference BorekColors — never duplicate hex values here.
 */

import { BorekColors } from "./colors.js";
import { BorekGrid } from "./grid.js";

/** Line weights in points (PptxGenJS line width convention). */
export const BorekBorderLineWidths = {
  card: 1,
  divider: 1,
} as const;

export type BorekBorderLineWidthRole = keyof typeof BorekBorderLineWidths;

export type BorekBorderLineWidthPt = (typeof BorekBorderLineWidths)[BorekBorderLineWidthRole];

export const BorekBorders = {
  card: {
    borderColor: BorekColors.border,
    borderRadiusInches: BorekGrid.rowGap / 2,
    lineWidthPt: BorekBorderLineWidths.card,
  },
  divider: {
    color: BorekColors.border,
    lineWidthPt: BorekBorderLineWidths.divider,
  },
} as const;

export type BorekBorderToken = keyof typeof BorekBorders;

export const BorekBorderTokens = {
  borders: BorekBorders,
  lineWidths: BorekBorderLineWidths,
} as const;

/** All border tokens as a plain record (for tests and future theme wiring). */
export const BOREK_BORDER_TOKENS = BorekBorderTokens;
