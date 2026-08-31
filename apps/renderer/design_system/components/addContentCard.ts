/**
 * AT-22: Generic content card component — title + description (technical plan v2 §17.1).
 *
 * Rounded card shape with bordered container and token-driven typography.
 * Layout renderers (BT-18 CONTEXT_01 ContentBlock, AT-29 architecture nodes, etc.)
 * must call this — never define their own card styling.
 */

import type PptxGenJS from "pptxgenjs";

import { BorekBorders } from "../tokens/borders.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekSpacing } from "../tokens/spacing.js";
import { BorekTypography } from "../tokens/typography.js";

/** PptxGenJS shape name for bordered content cards. */
export const CONTENT_CARD_SHAPE = "roundRect" as const;

export interface ContentCardRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Semantic card payload — matches SlideSpec ContentBlock (title + description). */
export interface ContentCardContent {
  title: string;
  description: string;
}

export interface ContentCardTextLayout {
  title: ContentCardRect;
  description: ContentCardRect;
}

/** Inner padding derived from grid/spacing tokens (AT-13). */
export function contentCardPadding(): number {
  return BorekGrid.rowGap;
}

/** Title band height inside a card — derived from footer height token. */
export function contentCardTitleBandHeight(): number {
  return BorekSpacing.footerHeight;
}

/** Compute title/description text regions inside a card rectangle. */
export function computeContentCardTextLayout(rect: ContentCardRect): ContentCardTextLayout {
  const pad = contentCardPadding();
  const titleH = contentCardTitleBandHeight();
  const innerW = rect.w - pad * 2;
  const titleGap = pad / 2;

  return {
    title: {
      x: rect.x + pad,
      y: rect.y + pad,
      w: innerW,
      h: titleH,
    },
    description: {
      x: rect.x + pad,
      y: rect.y + pad + titleH + titleGap,
      w: innerW,
      h: Math.max(rect.h - pad * 2 - titleH - titleGap, pad),
    },
  };
}

/** Card chrome — fill, border, and corner radius from border/color tokens (AT-11). */
export function contentCardShapeOptions(rect: ContentCardRect) {
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

/** Card title styling — compact heading typography. */
export function contentCardTitleTextOptions(layout: ContentCardTextLayout) {
  const { title } = layout;

  return {
    x: title.x,
    y: title.y,
    w: title.w,
    h: title.h,
    color: BorekColors.text,
    fontFace: BorekTypography.fonts.heading,
    fontSize: BorekTypography.defaultSizes.body,
    bold: true,
    align: "left" as const,
    valign: "top" as const,
    wrap: true,
    shrinkText: true,
  };
}

/** Card description styling — body typography with muted color. */
export function contentCardDescriptionTextOptions(layout: ContentCardTextLayout) {
  const { description } = layout;

  return {
    x: description.x,
    y: description.y,
    w: description.w,
    h: description.h,
    color: BorekColors.mutedText,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "left" as const,
    valign: "top" as const,
    wrap: true,
    shrinkText: true,
  };
}

/**
 * Render a generic title+description card at the given slide coordinates.
 *
 * @example
 * addContentCard(slide, { x: 1, y: 2, w: 4, h: 2.5 }, { title: "Problem", description: "..." });
 */
export function addContentCard(
  slide: PptxGenJS.Slide,
  rect: ContentCardRect,
  content: ContentCardContent,
): void {
  const textLayout = computeContentCardTextLayout(rect);

  slide.addShape(CONTENT_CARD_SHAPE, contentCardShapeOptions(rect));
  slide.addText(content.title, contentCardTitleTextOptions(textLayout));
  slide.addText(content.description, contentCardDescriptionTextOptions(textLayout));
}
