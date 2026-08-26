/**
 * AT-27: Native PowerPoint chart component (technical plan v2 §17.1, §17.4).
 *
 * Supports bar, line, pie, and doughnut chart types with token-driven colors
 * and typography. Layout renderers must call this — never define their own chart styling.
 */

import type PptxGenJS from "pptxgenjs";

import { BorekColors, type BorekColorHex } from "../tokens/colors.js";
import { BorekTypography } from "../tokens/typography.js";

/** MVP chart kinds required by backlog AT-27 and technical plan §17.4. */
export const SUPPORTED_CHART_KINDS = ["bar", "line", "pie", "doughnut"] as const;

export type ChartKind = (typeof SUPPORTED_CHART_KINDS)[number];

export interface ChartRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface ChartSeries {
  name: string;
  labels: readonly string[];
  values: readonly number[];
}

export interface ChartContent {
  series: readonly ChartSeries[];
}

type ChartDataRow = {
  name: string;
  labels: string[];
  values: number[];
};

/** Brand palette for chart series — derived from color tokens only (AT-11). */
export function borekChartColorPalette(): readonly BorekColorHex[] {
  return [
    BorekColors.primary,
    BorekColors.mutedText,
    BorekColors.text,
    BorekColors.border,
  ] as const;
}

export function isSupportedChartKind(kind: string): kind is ChartKind {
  return (SUPPORTED_CHART_KINDS as readonly string[]).includes(kind);
}

/** Validate a single series before rendering. */
export function validateChartSeries(series: ChartSeries): void {
  if (series.labels.length !== series.values.length) {
    throw new Error(
      `Chart series "${series.name}" has ${series.values.length} values for ${series.labels.length} labels`,
    );
  }
}

/** Map semantic chart content to PptxGenJS chart data rows. */
export function buildChartData(content: ChartContent): ChartDataRow[] {
  if (content.series.length === 0) {
    return [];
  }

  return content.series.map((series) => {
    validateChartSeries(series);

    return {
      name: series.name,
      labels: [...series.labels],
      values: [...series.values],
    };
  });
}

/** Shared axis/legend typography and colors from design tokens (AT-11, AT-12). */
export function chartTypographyOptions() {
  return {
    catAxisLabelFontFace: BorekTypography.fonts.body,
    catAxisLabelFontSize: BorekTypography.defaultSizes.body,
    catAxisLabelColor: BorekColors.mutedText,
    valAxisLabelFontFace: BorekTypography.fonts.body,
    valAxisLabelFontSize: BorekTypography.defaultSizes.body,
    valAxisLabelColor: BorekColors.mutedText,
    catAxisLineColor: BorekColors.border,
    valAxisLineColor: BorekColors.border,
    legendFontFace: BorekTypography.fonts.body,
    legendFontSize: BorekTypography.defaultSizes.body,
    legendColor: BorekColors.text,
  };
}

/** Chart placement and styling options for slide.addChart(). */
export function chartOptions(rect: ChartRect) {
  return {
    x: rect.x,
    y: rect.y,
    w: rect.w,
    h: rect.h,
    chartColors: [...borekChartColorPalette()],
    showLegend: true,
    legendPos: "b" as const,
    ...chartTypographyOptions(),
  };
}

/**
 * Render a native editable PowerPoint chart inside the given slide region.
 *
 * @example
 * addChart(slide, { x: 1, y: 2, w: 6, h: 3.5 }, "bar", {
 *   series: [{ name: "Auto-match rate", labels: ["Q1", "Q2", "Q3"], values: [62, 74, 85] }],
 * });
 */
export function addChart(
  slide: PptxGenJS.Slide,
  rect: ChartRect,
  kind: ChartKind,
  content: ChartContent,
): void {
  if (!isSupportedChartKind(kind)) {
    throw new Error(
      `Unsupported chart kind "${kind}". Supported kinds: ${SUPPORTED_CHART_KINDS.join(", ")}`,
    );
  }

  const chartData = buildChartData(content);
  if (chartData.length === 0) {
    return;
  }

  slide.addChart(kind, chartData, chartOptions(rect));
}
