/**
 * AT-23: Stat/value KPI card component (technical plan v2 §17.1).
 *
 * Rounded card with prominent value (+ optional unit) and label text.
 * Used by cover stat badges (BT-17 COVER_01) and success-metrics layouts.
 * Layout renderers must call this — never define their own stat-badge styling.
 */

import type PptxGenJS from "pptxgenjs";

import {
  CONTENT_CARD_SHAPE,
  contentCardPadding,
  type ContentCardRect,
} from "./addContentCard.js";
import { BorekBorders } from "../tokens/borders.js";
import { BorekColors, type BorekColorHex } from "../tokens/colors.js";
import { BorekTypography } from "../tokens/typography.js";

export const KPI_CARD_SHAPE = CONTENT_CARD_SHAPE;

export type KpiCardRect = ContentCardRect;

/** Semantic KPI payload — aligns with backlog value + unit + label and COVER_01 StatBadge. */
export interface KpiCardContent {
  value: string;
  /** Optional suffix (e.g. "%") — omit when the unit is already part of value. */
  unit?: string;
  label: string;
}

export type KpiCardVariant = "light" | "inverse";

export interface KpiCardTextLayout {
  value: KpiCardRect;
  label: KpiCardRect;
}

/** Inner padding — reuses AT-22 card padding token. */
export function kpiCardPadding(): number {
  return contentCardPadding();
}

/** Value band height inside a KPI card — half of inner height after padding. */
export function kpiCardValueBandHeight(rect: KpiCardRect): number {
  const pad = kpiCardPadding();
  const innerH = Math.max(rect.h - pad * 2, pad);
  return innerH / 2;
}

/** Compose display value from value + optional unit (technical plan §17.1 example). */
export function formatKpiDisplayValue(content: Pick<KpiCardContent, "value" | "unit">): string {
  const unit = content.unit ?? "";
  return unit.length > 0 ? `${content.value}${unit}` : content.value;
}

/** Compute value/label text regions inside a KPI card rectangle. */
export function computeKpiCardTextLayout(rect: KpiCardRect): KpiCardTextLayout {
  const pad = kpiCardPadding();
  const valueH = kpiCardValueBandHeight(rect);
  const innerW = rect.w - pad * 2;
  const labelGap = pad / 2;

  return {
    value: {
      x: rect.x + pad,
      y: rect.y + pad,
      w: innerW,
      h: valueH,
    },
    label: {
      x: rect.x + pad,
      y: rect.y + pad + valueH + labelGap,
      w: innerW,
      h: Math.max(rect.h - pad * 2 - valueH - labelGap, pad),
    },
  };
}

export function resolveKpiCardColors(variant: KpiCardVariant): {
  fill: BorekColorHex;
  border: BorekColorHex;
  value: BorekColorHex;
  label: BorekColorHex;
} {
  if (variant === "inverse") {
    return {
      fill: BorekColors.coverBackground,
      border: BorekColors.background,
      value: BorekColors.background,
      label: BorekColors.background,
    };
  }

  return {
    fill: BorekColors.background,
    border: BorekBorders.card.borderColor,
    value: BorekColors.text,
    label: BorekColors.mutedText,
  };
}

/** Card chrome — fill, border, and corner radius from tokens (AT-11, AT-22). */
export function kpiCardShapeOptions(rect: KpiCardRect, variant: KpiCardVariant = "light") {
  const colors = resolveKpiCardColors(variant);
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
    rectRadius: card.borderRadiusInches,
  };
}

/** KPI value styling — prominent heading font at body size (fits compact stat-badge regions). */
export function kpiCardValueTextOptions(layout: KpiCardTextLayout, variant: KpiCardVariant = "light") {
  const { value } = layout;
  const colors = resolveKpiCardColors(variant);

  return {
    x: value.x,
    y: value.y,
    w: value.w,
    h: value.h,
    color: colors.value,
    fontFace: BorekTypography.fonts.heading,
    fontSize: BorekTypography.defaultSizes.body,
    bold: true,
    align: "center" as const,
    valign: "middle" as const,
  };
}

/** KPI label styling — muted body typography beneath the value. */
export function kpiCardLabelTextOptions(layout: KpiCardTextLayout, variant: KpiCardVariant = "light") {
  const { label } = layout;
  const colors = resolveKpiCardColors(variant);

  return {
    x: label.x,
    y: label.y,
    w: label.w,
    h: label.h,
    color: colors.label,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "center" as const,
    valign: "top" as const,
  };
}

export type AddKpiCardOptions = {
  /** light = content slides; inverse = cover stat badges on dark background. */
  variant?: KpiCardVariant;
};

/**
 * Render a stat/value KPI card at the given slide coordinates.
 *
 * @example
 * addKpiCard(slide, { x: 1.1, y: 2.5, w: 3.2, h: 0.7 }, {
 *   value: "85",
 *   unit: "%",
 *   label: "Target auto-match rate",
 * });
 */
export function addKpiCard(
  slide: PptxGenJS.Slide,
  rect: KpiCardRect,
  content: KpiCardContent,
  options: AddKpiCardOptions = {},
): void {
  const variant = options.variant ?? "light";
  const textLayout = computeKpiCardTextLayout(rect);
  const displayValue = formatKpiDisplayValue(content);

  slide.addShape(KPI_CARD_SHAPE, kpiCardShapeOptions(rect, variant));
  slide.addText(displayValue, kpiCardValueTextOptions(textLayout, variant));
  slide.addText(content.label, kpiCardLabelTextOptions(textLayout, variant));
}
