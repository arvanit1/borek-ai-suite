/**
 * AT-26: Native PowerPoint data table component (technical plan v2 §17.1, §17.4).
 *
 * Token-driven header/body typography, borders, and cell margins.
 * Used by TEAM_FTE_01, REQUIREMENTS_MATRIX_01, and similar tabular layouts.
 * Layout renderers must call this — never define their own table styling.
 */

import type PptxGenJS from "pptxgenjs";

import { BorekBorders } from "../tokens/borders.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekTypography } from "../tokens/typography.js";

export interface DataTableRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Tabular payload — header row plus body rows of equal column width. */
export interface DataTableContent {
  headers: readonly string[];
  rows: readonly (readonly string[])[];
}

type TableCell = { text: string; options?: Record<string, unknown> };
type TableRow = TableCell[];

/** Inner cell margin — derived from grid spacing token (AT-13). */
export function dataTableCellMarginInches(): number {
  return BorekGrid.rowGap / 2;
}

/** Shared table/cell border styling from border tokens (AT-11). */
export function dataTableBorderOptions() {
  const { divider } = BorekBorders;

  return {
    type: "solid" as const,
    color: divider.color,
    pt: divider.lineWidthPt,
  };
}

/** Header cell styling — bold body typography with token colors. */
export function dataTableHeaderCellOptions() {
  const border = dataTableBorderOptions();

  return {
    bold: true,
    color: BorekColors.text,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    valign: "middle" as const,
    margin: dataTableCellMarginInches(),
    border,
    fill: { color: BorekColors.background },
  };
}

/** Body cell styling — standard body typography with token colors. */
export function dataTableBodyCellOptions() {
  const border = dataTableBorderOptions();

  return {
    color: BorekColors.text,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    valign: "middle" as const,
    margin: dataTableCellMarginInches(),
    border,
    fill: { color: BorekColors.background },
  };
}

/** Map semantic table content to native PptxGenJS table rows. */
export function buildDataTableRows(content: DataTableContent): TableRow[] {
  const columnCount = content.headers.length;
  if (columnCount === 0) {
    return [];
  }

  const headerOptions = dataTableHeaderCellOptions();
  const bodyOptions = dataTableBodyCellOptions();

  const headerRow: TableRow = content.headers.map((text) => ({
    text,
    options: headerOptions,
  }));

  const bodyRows: TableRow[] = content.rows.map((row) => {
    if (row.length !== columnCount) {
      throw new Error(
        `DataTable row has ${row.length} columns; expected ${columnCount} to match headers`,
      );
    }

    return row.map((text) => ({
      text,
      options: bodyOptions,
    }));
  });

  return [headerRow, ...bodyRows];
}

/**
 * Per-column widths for slide.addTable().
 * PptxGenJS requires an array when `w` is also set; a scalar colW is ignored and
 * defaults to ~5" total width, breaking layouts like REQUIREMENTS_MATRIX_01 (BT-24).
 */
export function dataTableColumnWidths(rect: DataTableRect, columnCount: number): number[] {
  if (columnCount <= 0) {
    return [];
  }

  const columnWidth = rect.w / columnCount;
  return Array.from({ length: columnCount }, () => columnWidth);
}

/** Table placement and sizing options for slide.addTable(). */
export function dataTableOptions(rect: DataTableRect, rowCount: number, columnCount: number) {
  return {
    x: rect.x,
    y: rect.y,
    w: rect.w,
    h: rect.h,
    colW: dataTableColumnWidths(rect, columnCount),
    rowH: rect.h / rowCount,
    border: dataTableBorderOptions(),
    color: BorekColors.text,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    valign: "middle" as const,
    margin: dataTableCellMarginInches(),
  };
}

/**
 * Render a native editable PowerPoint table inside the given slide region.
 *
 * @example
 * addDataTable(slide, { x: 1, y: 2, w: 8, h: 2.5 }, {
 *   headers: ["Role", "FTE", "Responsibility"],
 *   rows: [["Process owner", "0.3", "Approve matching rules"]],
 * });
 */
export function addDataTable(
  slide: PptxGenJS.Slide,
  rect: DataTableRect,
  content: DataTableContent,
): void {
  if (content.headers.length === 0) {
    return;
  }

  const tableRows = buildDataTableRows(content);
  const rowCount = tableRows.length;

  slide.addTable(
    tableRows,
    dataTableOptions(rect, rowCount, content.headers.length),
  );
}
