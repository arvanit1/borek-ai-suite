/** AT-27 unit checks executed by pytest via `npm run test:at27 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  SUPPORTED_CHART_KINDS,
  addChart,
  borekChartColorPalette,
  buildChartData,
  chartOptions,
  chartTypographyOptions,
  isSupportedChartKind,
  validateChartSeries,
} from "./addChart.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
import { BorekColors } from "../tokens/colors.js";
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

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addChart.ts");

const CHART_RECT = { x: 1.2, y: 2.1, w: 6.0, h: 3.4 };
const CHART_CONTENT = {
  series: [
    {
      name: "Auto-match rate",
      labels: ["Pilot", "Wave 1", "Wave 2"],
      values: [62, 74, 85],
    },
  ],
};

assert.ok(existsSync(COMPONENT_TS), "addChart.ts must exist");
assert.deepEqual([...SUPPORTED_CHART_KINDS], ["bar", "line", "pie", "doughnut"]);
assert.equal(isSupportedChartKind("bar"), true);
assert.equal(isSupportedChartKind("scatter"), false);

assert.deepEqual(borekChartColorPalette(), [
  BorekColors.primary,
  BorekColors.mutedText,
  BorekColors.text,
  BorekColors.border,
]);

const typography = chartTypographyOptions();
assert.equal(typography.catAxisLabelFontFace, BorekTypography.fonts.body);
assert.equal(typography.catAxisLabelFontSize, BorekTypography.defaultSizes.body);
assert.equal(typography.catAxisLabelColor, BorekColors.mutedText);
assert.equal(typography.legendColor, BorekColors.text);

const chartData = buildChartData(CHART_CONTENT);
assert.equal(chartData.length, 1);
assert.deepEqual(chartData[0]?.labels, ["Pilot", "Wave 1", "Wave 2"]);
assert.deepEqual(chartData[0]?.values, [62, 74, 85]);

const options = chartOptions(CHART_RECT);
assert.equal(options.x, CHART_RECT.x);
assert.equal(options.w, CHART_RECT.w);
assert.deepEqual(options.chartColors, [...borekChartColorPalette()]);
assert.equal(options.showLegend, true);

assert.throws(
  () => validateChartSeries({ name: "Mismatch", labels: ["A"], values: [1, 2] }),
  /has 2 values for 1 labels/,
);

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

const pptx = new PptxGenJS();
registerMasterContent(pptx);
const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
addChart(slide, CHART_RECT, "bar", CHART_CONTENT);

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));

const zip = await JSZip.loadAsync(buffer);
const chartPath = Object.keys(zip.files).find((path) => /ppt\/charts\/chart1\.xml$/.test(path));
assert.ok(chartPath, "pptx must contain chart1.xml");

const chartXml = await zip.file(chartPath)?.async("string");
assert.ok(chartXml, "chart1.xml must be readable");
assert.match(chartXml, /<c:barChart/, "native bar chart markup must be present");
assert.match(
  chartXml,
  new RegExp(`<a:srgbClr val="${BorekColors.primary}"/>`),
  "chart series must use BorekColors.primary",
);

for (const kind of ["line", "pie", "doughnut"] as const) {
  const kindPptx = new PptxGenJS();
  registerMasterContent(kindPptx);
  const kindSlide = kindPptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  addChart(kindSlide, CHART_RECT, kind, CHART_CONTENT);
  const kindBuffer = await kindPptx.write({ outputType: "nodebuffer" });
  const kindZip = await JSZip.loadAsync(kindBuffer);
  const kindChartPath = Object.keys(kindZip.files).find((path) =>
    /ppt\/charts\/chart\d+\.xml$/i.test(path),
  );
  assert.ok(kindChartPath, `${kind} chart must produce native chart XML`);
  const kindChartXml = await kindZip.file(kindChartPath)?.async("string");
  assert.ok(kindChartXml, `${kind} chart XML must be readable`);
  const expectedTag =
    kind === "line" ? "<c:lineChart" : kind === "pie" ? "<c:pieChart" : "<c:doughnutChart";
  assert.match(kindChartXml!, new RegExp(expectedTag), `${kind} chart markup must be present`);
}

process.stdout.write("AT-27 renderer unit checks passed\n");
