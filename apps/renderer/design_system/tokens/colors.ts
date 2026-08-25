/**
 * AT-11: Borek brand color tokens (technical plan v2 §16 — BorekTheme.colors).
 *
 * Single source for every brand color used in the renderer. Layout and component
 * implementations must import by token name — never hardcode hex values.
 *
 * Hex values omit the leading `#` (PptxGenJS convention).
 */

export const BorekColors = {
  background: "FFFFFF",
  text: "182230",
  mutedText: "667085",
  border: "E4E7EC",
  primary: "0057B8",
} as const;

export type BorekColorToken = keyof typeof BorekColors;

export type BorekColorHex = (typeof BorekColors)[BorekColorToken];

/** All brand colors as a plain record (for tests and future theme wiring). */
export const BOREK_COLOR_TOKENS: Readonly<Record<BorekColorToken, BorekColorHex>> = BorekColors;
