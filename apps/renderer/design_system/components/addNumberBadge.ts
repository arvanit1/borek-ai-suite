/**
 * AT-24: Numbered circle badge component (technical plan v2 §17.1).
 *
 * Filled circle with centered sequence number for architecture nodes,
 * process phases, and other numbered-list layouts.
 * Layout renderers must call this — never define their own step-number styling.
 */

import type PptxGenJS from "pptxgenjs";

import { BorekBorders } from "../tokens/borders.js";
import { BorekColors, type BorekColorHex } from "../tokens/colors.js";
import { BorekSpacing } from "../tokens/spacing.js";
import { BorekTypography } from "../tokens/typography.js";

/** PptxGenJS shape name for numbered circle badges. */
export const NUMBER_BADGE_SHAPE = "ellipse" as const;

export interface NumberBadgeRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export type NumberBadgeVariant = "filled" | "outline";

/** Default square diameter for numbered badges — derived from footer height token (AT-13). */
export function numberBadgeDiameter(): number {
  return BorekSpacing.footerHeight;
}

/** Build a square badge bounding box at the top-left anchor. */
export function numberBadgeRectAt(x: number, y: number, size: number = numberBadgeDiameter()): NumberBadgeRect {
  return { x, y, w: size, h: size };
}

/** Render label for a 1-based or arbitrary integer sequence number. */
export function formatNumberBadgeLabel(number: number): string {
  return String(number);
}

export function resolveNumberBadgeColors(variant: NumberBadgeVariant): {
  fill: BorekColorHex;
  border: BorekColorHex;
  text: BorekColorHex;
} {
  if (variant === "outline") {
    return {
      fill: BorekColors.background,
      border: BorekColors.primary,
      text: BorekColors.primary,
    };
  }

  return {
    fill: BorekColors.primary,
    border: BorekColors.primary,
    text: BorekColors.background,
  };
}

/** Circle chrome — fill and border from color tokens (AT-11). */
export function numberBadgeShapeOptions(rect: NumberBadgeRect, variant: NumberBadgeVariant = "filled") {
  const colors = resolveNumberBadgeColors(variant);
  const { card } = BorekBorders;

  return {
    x: rect.x,
    y: rect.y,
    w: rect.w,
    h: rect.h,
    fill: { color: colors.fill },
    line: {
      color: colors.border,
      width: card.lineWidthPt,
    },
  };
}

/** Centered number typography inside the badge circle. */
export function numberBadgeTextOptions(rect: NumberBadgeRect, variant: NumberBadgeVariant = "filled") {
  const colors = resolveNumberBadgeColors(variant);

  return {
    x: rect.x,
    y: rect.y,
    w: rect.w,
    h: rect.h,
    color: colors.text,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    bold: true,
    align: "center" as const,
    valign: "middle" as const,
  };
}

export type AddNumberBadgeOptions = {
  /** filled = primary circle (default); outline = light fill with primary ring/text. */
  variant?: NumberBadgeVariant;
};

/**
 * Render a numbered circle badge at the given slide coordinates.
 *
 * @example
 * addNumberBadge(slide, numberBadgeRectAt(1.0, 2.0), phase.number);
 */
export function addNumberBadge(
  slide: PptxGenJS.Slide,
  rect: NumberBadgeRect,
  number: number,
  options: AddNumberBadgeOptions = {},
): void {
  const variant = options.variant ?? "filled";
  const label = formatNumberBadgeLabel(number);

  slide.addShape(NUMBER_BADGE_SHAPE, numberBadgeShapeOptions(rect, variant));
  slide.addText(label, numberBadgeTextOptions(rect, variant));
}
