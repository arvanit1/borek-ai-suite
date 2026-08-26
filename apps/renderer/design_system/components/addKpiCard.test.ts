/** AT-23 unit checks executed by pytest via `npm run test:at23 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  KPI_CARD_SHAPE,
  addKpiCard,
  computeKpiCardTextLayout,
  formatKpiDisplayValue,
  kpiCardLabelTextOptions,
  kpiCardPadding,
  kpiCardShapeOptions,
  kpiCardValueBandHeight,
  kpiCardValueTextOptions,
  resolveKpiCardColors,
} from "./addKpiCard.js";
import { contentCardPadding } from "./addContentCard.js";
import {
  computeMasterCoverLayout,
  registerMasterCover,
  MASTER_COVER_NAME,
  MASTER_COVER_STAT_BADGE_PLACEHOLDER_1,
} from "../masters/MASTER_COVER.js";
import { BorekBorders } from "../tokens/borders.js";
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

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addKpiCard.ts");

const KPI_RECT = { x: 1.1, y: 2.5, w: 3.2, h: 0.7 };
const KPI_VALUE = "85";
const KPI_UNIT = "%";
const KPI_LABEL = "Target auto-match rate";

assert.ok(existsSync(COMPONENT_TS), "addKpiCard.ts must exist");
assert.equal(KPI_CARD_SHAPE, "roundRect");
assert.equal(kpiCardPadding(), contentCardPadding());
assert.equal(formatKpiDisplayValue({ value: KPI_VALUE, unit: KPI_UNIT }), "85%");
assert.equal(formatKpiDisplayValue({ value: "94/100" }), "94/100");

const textLayout = computeKpiCardTextLayout(KPI_RECT);
const pad = kpiCardPadding();
const valueH = kpiCardValueBandHeight(KPI_RECT);
assert.equal(textLayout.value.x, KPI_RECT.x + pad);
assert.equal(textLayout.value.y, KPI_RECT.y + pad);
assert.equal(textLayout.value.w, KPI_RECT.w - pad * 2);
assert.equal(textLayout.value.h, valueH);

const lightColors = resolveKpiCardColors("light");
assert.equal(lightColors.fill, BorekColors.background);
assert.equal(lightColors.border, BorekBorders.card.borderColor);
assert.equal(lightColors.value, BorekColors.text);
assert.equal(lightColors.label, BorekColors.mutedText);

const inverseColors = resolveKpiCardColors("inverse");
assert.equal(inverseColors.fill, BorekColors.coverBackground);
assert.equal(inverseColors.border, BorekColors.background);
assert.equal(inverseColors.value, BorekColors.background);

const lightShape = kpiCardShapeOptions(KPI_RECT, "light");
assert.equal(lightShape.fill.color, BorekColors.background);
assert.equal(lightShape.line.color, BorekBorders.card.borderColor);
assert.equal(lightShape.line.width, BorekBorders.card.lineWidthPt);
assert.equal(lightShape.rectRadius, BorekBorders.card.borderRadiusInches);

const valueOptions = kpiCardValueTextOptions(textLayout, "light");
assert.equal(valueOptions.color, BorekColors.text);
assert.equal(valueOptions.fontFace, BorekTypography.fonts.heading);
assert.equal(valueOptions.fontSize, BorekTypography.defaultSizes.body);
assert.equal(valueOptions.bold, true);
assert.equal(valueOptions.align, "center");

const labelOptions = kpiCardLabelTextOptions(textLayout, "light");
assert.equal(labelOptions.color, BorekColors.mutedText);
assert.equal(labelOptions.fontFace, BorekTypography.fonts.body);
assert.equal(labelOptions.fontSize, BorekTypography.defaultSizes.body);
assert.equal(labelOptions.align, "center");

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

const coverLayout = computeMasterCoverLayout();
const coverBadgeRect = coverLayout.statBadges[0];

const pptx = new PptxGenJS();
registerMasterCover(pptx);
const slide = pptx.addSlide({ masterName: MASTER_COVER_NAME });
addKpiCard(
  slide,
  coverBadgeRect,
  { value: KPI_VALUE, unit: KPI_UNIT, label: KPI_LABEL },
  { variant: "inverse" },
);

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));

const zip = await JSZip.loadAsync(buffer);
const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
assert.ok(slidePath, "pptx must contain slide1.xml");

const slideXml = await zip.file(slidePath)?.async("string");
assert.ok(slideXml, "slide1.xml must be readable");

assert.match(slideXml, new RegExp(formatKpiDisplayValue({ value: KPI_VALUE, unit: KPI_UNIT })));
assert.match(slideXml, new RegExp(KPI_LABEL));
assert.match(
  slideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.background}"/>`),
  "inverse KPI card must use light text/border on dark cover",
);
assert.match(slideXml, /roundRect|prst="roundRect"/, "slide must include a rounded-rectangle KPI card shape");
assert.equal(MASTER_COVER_STAT_BADGE_PLACEHOLDER_1, "statBadge1");

process.stdout.write("AT-23 renderer unit checks passed\n");
