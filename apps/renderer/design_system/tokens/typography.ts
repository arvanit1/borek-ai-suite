/**
 * Borek typography tokens (Brand Guide 2.0 / presentation_ci.json).
 *
 * Single source for heading/body font families and their default point sizes.
 * Layout and component code must import by token name — never inline font families or sizes.
 *
 * Font sizes use the PptxGenJS convention (numeric points).
 * Inter is primary; Verdana and system sans-serif are fallbacks only.
 */

export const BorekFontFamilies = {
  heading: "Inter",
  body: "Inter",
} as const;

export type BorekFontRole = keyof typeof BorekFontFamilies;

export type BorekFontFamily = (typeof BorekFontFamilies)[BorekFontRole];

/** Fallback chain when Inter is unavailable on the rendering host. */
export const BorekFontFallbacks = ["Segoe UI", "Verdana", "sans-serif"] as const;

/**
 * Default point sizes for each font role.
 * Body size meets Brand Guide minimum slide text (24px at 1920×1080 ≈ 18pt; use 24pt floor).
 */
export const BorekDefaultFontSizes = {
  heading: 32,
  body: 24,
} as const;

export type BorekFontSizeRole = keyof typeof BorekDefaultFontSizes;

export type BorekFontSizePt = (typeof BorekDefaultFontSizes)[BorekFontSizeRole];

export const BorekTypography = {
  fonts: BorekFontFamilies,
  fallbacks: BorekFontFallbacks,
  defaultSizes: BorekDefaultFontSizes,
} as const;

/** All typography tokens as a plain record (for tests and future theme wiring). */
export const BOREK_TYPOGRAPHY_TOKENS = BorekTypography;
