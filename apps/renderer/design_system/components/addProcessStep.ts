/**
 * AT-31: Numbered process-step component (technical plan v2 §17.1).
 *
 * Complete step block with badge, title, and description — distinct from addNumberBadge (AT-24).
 * Used by PROCESS_FLOW_01 (JJ-15). Layout renderers must call this — never define their own step styling.
 */

import type PptxGenJS from "pptxgenjs";

import {
  addNumberBadge,
  numberBadgeDiameter,
  type NumberBadgeRect,
} from "./addNumberBadge.js";
import { BorekBorders } from "../tokens/borders.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekSpacing } from "../tokens/spacing.js";
import { BorekTypography } from "../tokens/typography.js";

/** PptxGenJS shape name for bordered process-step blocks. */
export const PROCESS_STEP_SHAPE = "roundRect" as const;

export interface ProcessStepRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Semantic process step — aligns with PROCESS_FLOW_01 step items. */
export interface ProcessStepContent {
  number: number;
  title: string;
  description: string;
}

export interface ProcessStepTextRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface ProcessStepLayout {
  block: ProcessStepRect;
  badge: NumberBadgeRect;
  title: ProcessStepTextRect;
  description: ProcessStepTextRect;
}

/** Inner padding for the step block — from grid row gap (AT-13). */
export function processStepPadding(): number {
  return BorekGrid.rowGap;
}

/** Vertical gap between badge, title, and description bands. */
export function processStepVerticalGap(): number {
  return BorekGrid.rowGap;
}

/** Title band height inside a process step — derived from spacing token (AT-13). */
export function processStepTitleBandHeight(): number {
  return BorekSpacing.footerHeight;
}

/** Compute badge and text regions inside the caller-supplied step rectangle. */
export function computeProcessStepLayout(rect: ProcessStepRect): ProcessStepLayout {
  const pad = processStepPadding();
  const gap = processStepVerticalGap();
  const badgeSize = numberBadgeDiameter();
  const titleH = processStepTitleBandHeight();
  const innerW = rect.w - pad * 2;

  const badgeY = rect.y + pad;
  const titleY = badgeY + badgeSize + gap;
  const descriptionY = titleY + titleH + gap;

  return {
    block: rect,
    badge: {
      x: rect.x + (rect.w - badgeSize) / 2,
      y: badgeY,
      w: badgeSize,
      h: badgeSize,
    },
    title: {
      x: rect.x + pad,
      y: titleY,
      w: innerW,
      h: titleH,
    },
    description: {
      x: rect.x + pad,
      y: descriptionY,
      w: innerW,
      h: Math.max(rect.h - (descriptionY - rect.y) - pad, gap),
    },
  };
}

/** Outer step block chrome — bordered card from tokens (AT-11). */
export function processStepShapeOptions(rect: ProcessStepRect) {
  const { card } = BorekBorders;

  return {
    x: rect.x,
    y: rect.y,
    w: rect.w,
    h: rect.h,
    fill: { color: BorekColors.background },
    line: {
      color: card.borderColor,
      width: card.lineWidthPt,
    },
    rectRadius: card.borderRadiusInches,
  };
}

export function processStepTitleTextOptions(layout: ProcessStepTextRect) {
  return {
    x: layout.x,
    y: layout.y,
    w: layout.w,
    h: layout.h,
    color: BorekColors.text,
    fontFace: BorekTypography.fonts.heading,
    fontSize: BorekTypography.defaultSizes.body,
    bold: true,
    align: "center" as const,
    valign: "top" as const,
  };
}

export function processStepDescriptionTextOptions(layout: ProcessStepTextRect) {
  return {
    x: layout.x,
    y: layout.y,
    w: layout.w,
    h: layout.h,
    color: BorekColors.mutedText,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "center" as const,
    valign: "top" as const,
  };
}

/**
 * Render a numbered process step block at the given slide coordinates.
 *
 * @example
 * addProcessStep(slide, { x: 1.0, y: 2.0, w: 2.8, h: 2.2 }, {
 *   number: 1,
 *   title: "Capture invoice",
 *   description: "Read PDF and metadata from AP mailbox",
 * });
 */
export function addProcessStep(
  slide: PptxGenJS.Slide,
  position: ProcessStepRect,
  step: ProcessStepContent,
): void {
  const layout = computeProcessStepLayout(position);

  slide.addShape(PROCESS_STEP_SHAPE, processStepShapeOptions(layout.block));
  addNumberBadge(slide, layout.badge, step.number);
  slide.addText(step.title, processStepTitleTextOptions(layout.title));
  slide.addText(step.description, processStepDescriptionTextOptions(layout.description));
}
