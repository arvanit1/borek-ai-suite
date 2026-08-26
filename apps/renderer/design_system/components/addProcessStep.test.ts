/** AT-31 unit checks executed by pytest via `npm run test:at31 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import { formatNumberBadgeLabel } from "./addNumberBadge.js";
import {
  PROCESS_STEP_SHAPE,
  addProcessStep,
  computeProcessStepLayout,
  processStepDescriptionTextOptions,
  processStepPadding,
  processStepShapeOptions,
  processStepTitleTextOptions,
  processStepVerticalGap,
} from "./addProcessStep.js";
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

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addProcessStep.ts");

const STEP_RECT = { x: 1.2, y: 2.0, w: 2.8, h: 2.4 };
const STEP = {
  number: 2,
  title: "Match invoice",
  description: "Apply 3-way match rules against PO and receipt",
};

assert.ok(existsSync(COMPONENT_TS), "addProcessStep.ts must exist");
assert.equal(PROCESS_STEP_SHAPE, "roundRect");
assert.equal(processStepPadding(), BorekGrid.rowGap);
assert.equal(processStepVerticalGap(), BorekGrid.rowGap);

const layout = computeProcessStepLayout(STEP_RECT);
assert.equal(layout.badge.y, STEP_RECT.y + processStepPadding());
assert.equal(layout.badge.x, STEP_RECT.x + (STEP_RECT.w - layout.badge.w) / 2);
assert.ok(layout.title.y > layout.badge.y + layout.badge.h);
assert.ok(layout.description.y > layout.title.y);

const shapeOptions = processStepShapeOptions(STEP_RECT);
assert.equal(shapeOptions.fill.color, BorekColors.background);
assert.equal(shapeOptions.line.color, BorekBorders.card.borderColor);
assert.equal(shapeOptions.line.width, BorekBorders.card.lineWidthPt);

const titleOptions = processStepTitleTextOptions(layout.title);
assert.equal(titleOptions.color, BorekColors.text);
assert.equal(titleOptions.fontFace, BorekTypography.fonts.heading);
assert.equal(titleOptions.fontSize, BorekTypography.defaultSizes.body);
assert.equal(titleOptions.bold, true);

const descriptionOptions = processStepDescriptionTextOptions(layout.description);
assert.equal(descriptionOptions.color, BorekColors.mutedText);
assert.equal(descriptionOptions.fontFace, BorekTypography.fonts.body);
assert.equal(descriptionOptions.fontSize, BorekTypography.defaultSizes.body);

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);
assert.match(
  componentSource,
  /title:\s*string[\s\S]*description:\s*string/,
  "process step must accept title and description — distinct from addNumberBadge",
);

const pptx = new PptxGenJS();
registerMasterContent(pptx);
const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
addProcessStep(slide, STEP_RECT, STEP);

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));

const zip = await JSZip.loadAsync(buffer);
const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
assert.ok(slidePath, "pptx must contain slide1.xml");

const slideXml = await zip.file(slidePath)?.async("string");
assert.ok(slideXml, "slide1.xml must be readable");

assert.match(slideXml, new RegExp(STEP.title), "slide must contain process step title");
assert.match(slideXml, new RegExp(STEP.description), "slide must contain process step description");
assert.match(
  slideXml,
  new RegExp(formatNumberBadgeLabel(STEP.number)),
  "slide must contain numbered badge label",
);
assert.match(
  slideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.primary}"/>`),
  "process step badge must use BorekColors.primary",
);
assert.match(slideXml, /roundRect|prst="roundRect"/, "slide must include bordered step block");

process.stdout.write("AT-31 renderer unit checks passed\n");
