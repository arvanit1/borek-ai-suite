/** AT-30 unit checks executed by pytest via `npm run test:at30 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import { CONNECTOR_SHAPE, addConnector, connectorShapeOptions } from "./addConnector.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
import { BorekBorders } from "../tokens/borders.js";
import { BorekColors } from "../tokens/colors.js";

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

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addConnector.ts");

const FROM = { x: 1.5, y: 3.0 };
const TO = { x: 5.0, y: 4.2 };

assert.ok(existsSync(COMPONENT_TS), "addConnector.ts must exist");
assert.equal(CONNECTOR_SHAPE, "line");

const defaultOptions = connectorShapeOptions(FROM, TO);
assert.equal(defaultOptions.x, FROM.x);
assert.equal(defaultOptions.y, FROM.y);
assert.equal(defaultOptions.w, TO.x - FROM.x);
assert.equal(defaultOptions.h, TO.y - FROM.y);
assert.equal(defaultOptions.line.color, BorekColors.border);
assert.equal(defaultOptions.line.width, BorekBorders.divider.lineWidthPt);

const customOptions = connectorShapeOptions(FROM, TO, {
  color: BorekColors.primary,
  lineWidth: BorekBorders.card.lineWidthPt,
});
assert.equal(customOptions.line.color, BorekColors.primary);
assert.equal(customOptions.line.width, BorekBorders.card.lineWidthPt);

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

const pptx = new PptxGenJS();
registerMasterContent(pptx);
const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
addConnector(slide, FROM, TO);

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));

const zip = await JSZip.loadAsync(buffer);
const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
assert.ok(slidePath, "pptx must contain slide1.xml");

const slideXml = await zip.file(slidePath)?.async("string");
assert.ok(slideXml, "slide1.xml must be readable");

assert.match(slideXml, /line|prst="line"/, "slide must include a connector line shape");
assert.match(
  slideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.border}"/>`),
  "default connector must use BorekColors.border",
);

process.stdout.write("AT-30 renderer unit checks passed\n");
