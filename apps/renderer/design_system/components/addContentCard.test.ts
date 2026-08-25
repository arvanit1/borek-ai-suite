/** AT-22 unit checks executed by pytest via `npm run test:at22 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  CONTENT_CARD_SHAPE,
  addContentCard,
  computeContentCardTextLayout,
  contentCardDescriptionTextOptions,
  contentCardPadding,
  contentCardShapeOptions,
  contentCardTitleBandHeight,
  contentCardTitleTextOptions,
} from "./addContentCard.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
import { BorekBorders } from "../tokens/borders.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
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

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addContentCard.ts");

const CARD_RECT = { x: 1.1, y: 2.2, w: 4.5, h: 2.4 };
const CARD_TITLE = "Core Platform";
const CARD_DESCRIPTION = "Central orchestration layer connecting ERP, workflow, and audit systems.";

assert.ok(existsSync(COMPONENT_TS), "addContentCard.ts must exist");
assert.equal(CONTENT_CARD_SHAPE, "roundRect");
assert.equal(contentCardPadding(), BorekGrid.rowGap);
assert.equal(contentCardTitleBandHeight(), BorekSpacing.footerHeight);

const textLayout = computeContentCardTextLayout(CARD_RECT);
const pad = contentCardPadding();
assert.equal(textLayout.title.x, CARD_RECT.x + pad);
assert.equal(textLayout.title.y, CARD_RECT.y + pad);
assert.equal(textLayout.title.w, CARD_RECT.w - pad * 2);
assert.equal(textLayout.title.h, contentCardTitleBandHeight());

const shapeOptions = contentCardShapeOptions(CARD_RECT);
assert.equal(shapeOptions.fill.color, BorekColors.background);
assert.equal(shapeOptions.line.color, BorekBorders.card.borderColor);
assert.equal(shapeOptions.line.width, BorekBorders.card.lineWidthPt);
assert.equal(shapeOptions.rectRadius, BorekBorders.card.borderRadiusInches);

const titleOptions = contentCardTitleTextOptions(textLayout);
assert.equal(titleOptions.color, BorekColors.text);
assert.equal(titleOptions.fontFace, BorekTypography.fonts.heading);
assert.equal(titleOptions.fontSize, BorekTypography.defaultSizes.body);
assert.equal(titleOptions.bold, true);

const descriptionOptions = contentCardDescriptionTextOptions(textLayout);
assert.equal(descriptionOptions.color, BorekColors.mutedText);
assert.equal(descriptionOptions.fontFace, BorekTypography.fonts.body);
assert.equal(descriptionOptions.fontSize, BorekTypography.defaultSizes.body);

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

const pptx = new PptxGenJS();
registerMasterContent(pptx);
const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
addContentCard(slide, CARD_RECT, { title: CARD_TITLE, description: CARD_DESCRIPTION });

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));

const zip = await JSZip.loadAsync(buffer);
const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
assert.ok(slidePath, "pptx must contain slide1.xml");

const slideXml = await zip.file(slidePath)?.async("string");
assert.ok(slideXml, "slide1.xml must be readable");

assert.match(slideXml, new RegExp(CARD_TITLE), "slide must contain card title text");
assert.match(slideXml, new RegExp(CARD_DESCRIPTION), "slide must contain card description text");
assert.match(
  slideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.border}"/>`),
  "card border must use BorekColors.border",
);
assert.match(
  slideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.text}"/>`),
  "card title must use BorekColors.text",
);
assert.match(
  slideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.mutedText}"/>`),
  "card description must use BorekColors.mutedText",
);
assert.match(slideXml, /roundRect|prst="roundRect"/, "slide must include a rounded-rectangle card shape");

process.stdout.write("AT-22 renderer unit checks passed\n");
