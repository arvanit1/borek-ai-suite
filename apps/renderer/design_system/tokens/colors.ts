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
  /** Dark navy cover slide field — same hex as text for now; calibrate at AT-55 golden deck. */
  coverBackground: "182230",
} as const;

export type BorekColorToken = keyof typeof BorekColors;

export type BorekColorHex = (typeof BorekColors)[BorekColorToken];

/** Semantic statuses for REQUIREMENTS_MATRIX_01 (BT-8 / BT-21). SlideSpec carries strings only. */
export type RequirementStatus = "included" | "partial" | "later";

export const REQUIREMENT_STATUSES: readonly RequirementStatus[] = [
  "included",
  "partial",
  "later",
] as const;

/** Fill, text, and border hex for requirement status pills — derived from brand tokens above. */
export interface RequirementStatusColors {
  fill: BorekColorHex;
  text: BorekColorHex;
  border: BorekColorHex;
}

/**
 * Approved semantic status palette for requirement matrix pills.
 * Calibrate against golden deck at AT-55; layouts must not hardcode alternatives.
 */
export const BorekRequirementStatusColors: Record<RequirementStatus, RequirementStatusColors> = {
  included: {
    fill: BorekColors.primary,
    text: BorekColors.background,
    border: BorekColors.primary,
  },
  partial: {
    fill: BorekColors.background,
    text: BorekColors.primary,
    border: BorekColors.primary,
  },
  later: {
    fill: BorekColors.border,
    text: BorekColors.mutedText,
    border: BorekColors.border,
  },
};

/** All brand colors as a plain record (for tests and future theme wiring). */
export const BOREK_COLOR_TOKENS: Readonly<Record<BorekColorToken, BorekColorHex>> = BorekColors;
