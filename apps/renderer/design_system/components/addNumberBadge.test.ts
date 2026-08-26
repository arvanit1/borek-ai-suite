/** AT-24 unit checks executed by pytest via `npm run test:at24 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  NUMBER_BADGE_SHAPE,
  addNumberBadge,
  formatNumberBadgeLabel,
  numberBadgeDiameter,
  numberBadgeRectAt,
  numberBadgeShapeOptions,
  numberBadgeTextOptions,
  resolveNumberBadgeColors,
} from "./addNumberBadge.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
import { BorekBorders } from "../tokens/borders.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekSpacing } from "../tokens/spacing.js";
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

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addNumberBadge.ts");

const BADGE_NUMBER = 3;
const BADGE_RECT = numberBadgeRectAt(1.2, 2.4);

assert.ok(existsSync(COMPONENT_TS), "addNumberBadge.ts must exist");
assert.equal(NUMBER_BADGE_SHAPE, "ellipse");
assert.equal(numberBadgeDiameter(), BorekSpacing.footerHeight);
assert.deepEqual(BADGE_RECT, {
  x: 1.2,
  y: 2.4,
  w: BorekSpacing.footerHeight,
  h: BorekSpacing.footerHeight,
});
assert.equal(formatNumberBadgeLabel(BADGE_NUMBER), "3");

const filledColors = resolveNumberBadgeColors("filled");
assert.equal(filledColors.fill, BorekColors.primary);
assert.equal(filledColors.border, BorekColors.primary);
assert.equal(filledColors.text, BorekColors.background);

const outlineColors = resolveNumberBadgeColors("outline");
assert.equal(outlineColors.fill, BorekColors.background);
assert.equal(outlineColors.border, BorekColors.primary);
assert.equal(outlineColors.text, BorekColors.primary);

const shapeOptions = numberBadgeShapeOptions(BADGE_RECT, "filled");
assert.equal(shapeOptions.fill.color, BorekColors.primary);
assert.equal(shapeOptions.line.color, BorekColors.primary);
assert.equal(shapeOptions.line.width, BorekBorders.card.lineWidthPt);

const textOptions = numberBadgeTextOptions(BADGE_RECT, "filled");
assert.equal(textOptions.color, BorekColors.background);
assert.equal(textOptions.fontFace, BorekTypography.fonts.body);
assert.equal(textOptions.fontSize, BorekTypography.defaultSizes.body);
assert.equal(textOptions.bold, true);
assert.equal(textOptions.align, "center");
assert.equal(textOptions.valign, "middle");

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

const pptx = new PptxGenJS();
registerMasterContent(pptx);
const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
addNumberBadge(slide, BADGE_RECT, BADGE_NUMBER);

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));

const zip = await JSZip.loadAsync(buffer);
const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
assert.ok(slidePath, "pptx must contain slide1.xml");

const slideXml = await zip.file(slidePath)?.async("string");
assert.ok(slideXml, "slide1.xml must be readable");

assert.match(slideXml, new RegExp(formatNumberBadgeLabel(BADGE_NUMBER)));
assert.match(
  slideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.primary}"/>`),
  "filled badge must use BorekColors.primary",
);
assert.match(slideXml, /ellipse|prst="ellipse"/, "slide must include an ellipse badge shape");

process.stdout.write("AT-24 renderer unit checks passed\n");
