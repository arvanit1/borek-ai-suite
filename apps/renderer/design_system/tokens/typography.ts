/**
 * AT-12: Borek typography tokens (technical plan v2 §16 — BorekTheme.fonts).
 *
 * Single source for heading/body font families and their default point sizes.
 * Layout and component code must import by token name — never inline font families or sizes.
 *
 * Font sizes use the PptxGenJS convention (numeric points).
 */

export const BorekFontFamilies = {
  heading: "Aptos Display",
  body: "Aptos",
} as const;

export type BorekFontRole = keyof typeof BorekFontFamilies;

export type BorekFontFamily = (typeof BorekFontFamilies)[BorekFontRole];

/**
 * Default point sizes for each font role (backlog AT-12).
 * Named tokens only — values live here, never per layout (technical plan v2 §16).
 * Exact pt values calibrate against the approved reference deck in AT-55 golden tests.
 */
export const BorekDefaultFontSizes = {
  heading: 28,
  body: 12,
} as const;

export type BorekFontSizeRole = keyof typeof BorekDefaultFontSizes;

export type BorekFontSizePt = (typeof BorekDefaultFontSizes)[BorekFontSizeRole];

export const BorekTypography = {
  fonts: BorekFontFamilies,
  defaultSizes: BorekDefaultFontSizes,
} as const;

/** All typography tokens as a plain record (for tests and future theme wiring). */
export const BOREK_TYPOGRAPHY_TOKENS = BorekTypography;
