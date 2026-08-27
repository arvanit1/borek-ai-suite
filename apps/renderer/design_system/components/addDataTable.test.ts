/** AT-26 unit checks executed by pytest via `npm run test:at26 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  addDataTable,
  buildDataTableRows,
  dataTableBodyCellOptions,
  dataTableBorderOptions,
  dataTableCellMarginInches,
  dataTableColumnWidths,
  dataTableHeaderCellOptions,
  dataTableOptions,
  type DataTableRect,
} from "./addDataTable.js";
import { computeRequirementsMatrix01Layout } from "../../layouts/group_a/renderRequirementsMatrix01.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
import { BorekBorders } from "../tokens/borders.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekTypography } from "../tokens/typography.js";

const HARDCODED_HEX_PATTERN = /#?[0-9A-Fa-f]{6}\b/g;
const FONT_FAMILY_PATTERNS = [/["']Aptos Display["']/g, /["']Aptos["'](?!\s*Display)/g];
const INLINE_FONT_SIZE_PATTERN = /fontSize\s*:\s*\d+(?:\.\d+)?/g;

function findHardcodedHexInContent(content: string): string[] {
  return [...content.matchAll(HARDCODED_HEX_PATTERN)].map((match) => match[0]);
}

function findHardcodedFontFamilyInContent(content: string): string[] {
  const matches: string[] = [];
  for (const pattern of FONT_FAMILY_PATTERNS) {
    for (const match of content.matchAll(pattern)) {
      matches.push(match[0]);
    }
  }
  return matches;
}

function findInlineFontSizeInContent(content: string): string[] {
  return [...content.matchAll(INLINE_FONT_SIZE_PATTERN)].map((match) => match[0]);
}

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addDataTable.ts");

const EMU_PER_INCH = 914400;

const TABLE_RECT = { x: 1.0, y: 2.0, w: 8.0, h: 2.2 };
const TABLE_CONTENT = {
  headers: ["Role", "FTE", "Responsibility"],
  rows: [
    ["Process owner", "0.3", "Approve matching rules and exception decisions"],
    ["AP operator", "0.5", "Work the exception queue during pilot"],
  ],
};

assert.ok(existsSync(COMPONENT_TS), "addDataTable.ts must exist");
assert.equal(dataTableCellMarginInches(), BorekGrid.rowGap / 2);

const border = dataTableBorderOptions();
assert.equal(border.color, BorekBorders.divider.color);
assert.equal(border.pt, BorekBorders.divider.lineWidthPt);
assert.equal(border.type, "solid");

const headerOptions = dataTableHeaderCellOptions();
assert.equal(headerOptions.bold, true);
assert.equal(headerOptions.color, BorekColors.text);
assert.equal(headerOptions.fontFace, BorekTypography.fonts.body);
assert.equal(headerOptions.fontSize, BorekTypography.defaultSizes.body);

const bodyOptions = dataTableBodyCellOptions();
assert.equal(bodyOptions.color, BorekColors.text);
assert.equal(bodyOptions.fontFace, BorekTypography.fonts.body);
assert.equal(bodyOptions.fontSize, BorekTypography.defaultSizes.body);

const tableRows = buildDataTableRows(TABLE_CONTENT);
assert.equal(tableRows.length, 1 + TABLE_CONTENT.rows.length);
assert.equal(tableRows[0]?.length, TABLE_CONTENT.headers.length);
assert.equal(tableRows[0]?.[0]?.text, "Role");
assert.equal(tableRows[1]?.[1]?.text, "0.3");

const tableOptions = dataTableOptions(TABLE_RECT, tableRows.length, TABLE_CONTENT.headers.length);
const expectedColumnWidth = TABLE_RECT.w / TABLE_CONTENT.headers.length;
assert.deepEqual(
  tableOptions.colW,
  dataTableColumnWidths(TABLE_RECT, TABLE_CONTENT.headers.length),
);
assert.deepEqual(
  tableOptions.colW,
  Array.from({ length: TABLE_CONTENT.headers.length }, () => expectedColumnWidth),
);
assert.equal(tableOptions.rowH, TABLE_RECT.h / tableRows.length);
assert.equal(tableOptions.color, BorekColors.text);

function gridColumnWidthsInches(slideXml: string): number[] {
  const re = /<a:gridCol w="(\d+)"/g;
  const widths: number[] = [];
  for (const match of slideXml.matchAll(re)) {
    widths.push(Number(match[1]) / EMU_PER_INCH);
  }
  return widths;
}

function assertGridColumnsMatchRect(slideXml: string, rect: DataTableRect, columnCount: number): void {
  const gridCols = gridColumnWidthsInches(slideXml);
  assert.equal(
    gridCols.length,
    columnCount,
    `expected ${columnCount} gridCol entries in PPTX`,
  );
  const totalWidth = gridCols.reduce((sum, width) => sum + width, 0);
  assert.ok(
    Math.abs(totalWidth - rect.w) < 0.001,
    `gridCol total ${totalWidth.toFixed(3)}" must match rect.w ${rect.w.toFixed(3)}"`,
  );
  for (const width of gridCols) {
    assert.ok(
      Math.abs(width - rect.w / columnCount) < 0.001,
      `each gridCol must be ${(rect.w / columnCount).toFixed(3)}" wide`,
    );
  }
}

assert.throws(
  () =>
    buildDataTableRows({
      headers: ["A", "B"],
      rows: [["only-one-column"]],
    }),
  /expected 2 to match headers/,
);

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

const pptx = new PptxGenJS();
registerMasterContent(pptx);
const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
addDataTable(slide, TABLE_RECT, TABLE_CONTENT);

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));

const zip = await JSZip.loadAsync(buffer);
const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
assert.ok(slidePath, "pptx must contain slide1.xml");

const slideXml = await zip.file(slidePath)?.async("string");
assert.ok(slideXml, "slide1.xml must be readable");

assert.match(slideXml, /<a:tbl/, "slide must include native PowerPoint table markup");
assert.match(slideXml, /Process owner/);
assert.match(slideXml, /Approve matching rules and exception decisions/);
assert.match(
  slideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.border}"/>`),
  "table borders must use BorekColors.border",
);
assertGridColumnsMatchRect(slideXml, TABLE_RECT, TABLE_CONTENT.headers.length);

const requirementsMatrixRect = computeRequirementsMatrix01Layout(true, 6).tables[0];
assert.equal(
  requirementsMatrixRect.w.toFixed(3),
  "5.854",
  "BT-24 slide 5 uses side-by-side tables at 5.854 inches",
);

const pptxRequirementsMatrix = new PptxGenJS();
registerMasterContent(pptxRequirementsMatrix);
const requirementsMatrixSlide = pptxRequirementsMatrix.addSlide({ masterName: MASTER_CONTENT_NAME });
addDataTable(requirementsMatrixSlide, requirementsMatrixRect, {
  headers: ["Requirement", "Status"],
  rows: [
    ["A — Invoice field extraction", ""],
    ["B — Three-way matching", ""],
    ["C — Duplicate detection", ""],
  ],
});
const requirementsMatrixBuffer = await pptxRequirementsMatrix.write({ outputType: "nodebuffer" });
const requirementsMatrixZip = await JSZip.loadAsync(requirementsMatrixBuffer);
const requirementsMatrixXml = await requirementsMatrixZip
  .file("ppt/slides/slide1.xml")
  ?.async("string");
assert.ok(requirementsMatrixXml, "requirements matrix slide XML must be readable");
assertGridColumnsMatchRect(requirementsMatrixXml, requirementsMatrixRect, 2);

process.stdout.write("AT-26 renderer unit checks passed\n");
