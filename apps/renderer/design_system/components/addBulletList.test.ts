/** AT-25 unit checks executed by pytest via `npm run test:at25 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  BULLET_LIST_INCHES_TO_POINTS,
  addBulletList,
  buildBulletListTextRuns,
  bulletListContainerOptions,
  bulletListItemSpacingPt,
  resolveBulletListColor,
} from "./addBulletList.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
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

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addBulletList.ts");

const LIST_RECT = { x: 1.0, y: 2.0, w: 5.5, h: 3.0 };
const LIST_ITEMS = [
  "Invoice intake from the shared mailbox",
  "Field extraction with confidence",
  "Reasoned exception queue",
];

assert.ok(existsSync(COMPONENT_TS), "addBulletList.ts must exist");
assert.equal(bulletListItemSpacingPt(), BorekGrid.rowGap * BULLET_LIST_INCHES_TO_POINTS);
assert.equal(resolveBulletListColor("light"), BorekColors.text);
assert.equal(resolveBulletListColor("dark"), BorekColors.background);

const containerOptions = bulletListContainerOptions(LIST_RECT, "light");
assert.equal(containerOptions.x, LIST_RECT.x);
assert.equal(containerOptions.color, BorekColors.text);
assert.equal(containerOptions.fontFace, BorekTypography.fonts.body);
assert.equal(containerOptions.fontSize, BorekTypography.defaultSizes.body);
assert.equal(containerOptions.valign, "top");

const runs = buildBulletListTextRuns(LIST_ITEMS, "light");
assert.equal(runs.length, LIST_ITEMS.length);
assert.equal(runs[0]?.text, LIST_ITEMS[0]);
assert.equal(runs[0]?.options.bullet, true);
assert.equal(runs[0]?.options.breakLine, true);
assert.equal(runs[0]?.options.paraSpaceAfter, bulletListItemSpacingPt());
assert.equal(runs[0]?.options.fontFace, BorekTypography.fonts.body);
assert.equal(runs[0]?.options.fontSize, BorekTypography.defaultSizes.body);
assert.equal(runs[runs.length - 1]?.options.breakLine, false);
assert.equal(runs[runs.length - 1]?.options.paraSpaceAfter, 0);

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

const pptx = new PptxGenJS();
registerMasterContent(pptx);
const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
addBulletList(slide, LIST_RECT, LIST_ITEMS);

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));

const zip = await JSZip.loadAsync(buffer);
const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
assert.ok(slidePath, "pptx must contain slide1.xml");

const slideXml = await zip.file(slidePath)?.async("string");
assert.ok(slideXml, "slide1.xml must be readable");

for (const item of LIST_ITEMS) {
  assert.match(slideXml, new RegExp(item), `slide must contain bullet item "${item}"`);
}
assert.match(slideXml, /<a:buChar|<a:buFont|<a:buAutoNum/, "slide must include native PowerPoint bullet markup");

process.stdout.write("AT-25 renderer unit checks passed\n");
