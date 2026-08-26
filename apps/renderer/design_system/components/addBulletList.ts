/**
 * AT-25: Standard bullet list component (technical plan v2 §17.1).
 *
 * Token-driven body typography and grid-derived paragraph spacing.
 * Used by SCOPE_01, OPEN_QUESTIONS_01, NEXT_STEPS_01 checklist, and similar layouts.
 * Layout renderers must call this — never define their own bullet styling.
 */

import type PptxGenJS from "pptxgenjs";

import { BorekColors, type BorekColorHex } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekTypography } from "../tokens/typography.js";

export interface BulletListRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export type BulletListVariant = "light" | "dark";

/** PptxGenJS uses points; grid row gap is stored in inches (AT-13). */
export const BULLET_LIST_INCHES_TO_POINTS = 72;

/** Paragraph spacing between bullet items — derived from BorekGrid.rowGap. */
export function bulletListItemSpacingPt(): number {
  return BorekGrid.rowGap * BULLET_LIST_INCHES_TO_POINTS;
}

export function resolveBulletListColor(variant: BulletListVariant): BorekColorHex {
  return variant === "dark" ? BorekColors.background : BorekColors.text;
}

/** Shared list container styling — position and default body typography. */
export function bulletListContainerOptions(
  rect: BulletListRect,
  variant: BulletListVariant = "light",
) {
  return {
    x: rect.x,
    y: rect.y,
    w: rect.w,
    h: rect.h,
    color: resolveBulletListColor(variant),
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "left" as const,
    valign: "top" as const,
  };
}

/** Build per-item text runs with bullets and consistent paragraph spacing. */
export function buildBulletListTextRuns(
  items: readonly string[],
  variant: BulletListVariant = "light",
): Array<{ text: string; options: Record<string, unknown> }> {
  const spacing = bulletListItemSpacingPt();
  const color = resolveBulletListColor(variant);

  return items.map((text, index) => ({
    text,
    options: {
      bullet: true,
      breakLine: index < items.length - 1,
      paraSpaceAfter: index < items.length - 1 ? spacing : 0,
      color,
      fontFace: BorekTypography.fonts.body,
      fontSize: BorekTypography.defaultSizes.body,
    },
  }));
}

export type AddBulletListOptions = {
  /** light = dark text on light slides; dark = light text on dark slides (MASTER_CLOSING). */
  variant?: BulletListVariant;
};

/**
 * Render a standard bullet list inside the given slide region.
 *
 * @example
 * addBulletList(slide, { x: 1, y: 2, w: 5, h: 3 }, spec.included);
 */
export function addBulletList(
  slide: PptxGenJS.Slide,
  rect: BulletListRect,
  items: readonly string[],
  options: AddBulletListOptions = {},
): void {
  if (items.length === 0) {
    return;
  }

  const variant = options.variant ?? "light";
  slide.addText(buildBulletListTextRuns(items, variant), bulletListContainerOptions(rect, variant));
}
