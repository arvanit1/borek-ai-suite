/** AT-29 unit checks executed by pytest via `npm run test:at29 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  addArchitectureNode,
  architectureNodeBadgeSize,
  computeArchitectureNodeLayout,
} from "./addArchitectureNode.js";
import { formatNumberBadgeLabel, numberBadgeDiameter } from "./addNumberBadge.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekSpacing } from "../tokens/spacing.js";

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

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addArchitectureNode.ts");

const NODE_RECT = { x: 2.0, y: 2.5, w: 3.4, h: 1.5 };
const NODE = {
  number: 1,
  title: "AP Mailbox",
  description: "Source of invoices, read-only",
};

assert.ok(existsSync(COMPONENT_TS), "addArchitectureNode.ts must exist");
assert.equal(architectureNodeBadgeSize(), numberBadgeDiameter());
assert.equal(architectureNodeBadgeSize(), BorekSpacing.footerHeight);

const layout = computeArchitectureNodeLayout(NODE_RECT);
const badgeHalf = architectureNodeBadgeSize() / 2;
assert.equal(layout.badge.x, NODE_RECT.x - badgeHalf);
assert.equal(layout.badge.y, NODE_RECT.y - badgeHalf);
assert.equal(layout.badge.w, architectureNodeBadgeSize());
assert.equal(layout.badge.h, architectureNodeBadgeSize());
assert.deepEqual(layout.card, NODE_RECT);

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

const pptx = new PptxGenJS();
registerMasterContent(pptx);
const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
addArchitectureNode(slide, NODE_RECT, NODE);

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));

const zip = await JSZip.loadAsync(buffer);
const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
assert.ok(slidePath, "pptx must contain slide1.xml");

const slideXml = await zip.file(slidePath)?.async("string");
assert.ok(slideXml, "slide1.xml must be readable");

assert.match(slideXml, new RegExp(NODE.title), "slide must contain architecture node title");
assert.match(slideXml, new RegExp(NODE.description), "slide must contain architecture node description");
assert.match(
  slideXml,
  new RegExp(formatNumberBadgeLabel(NODE.number)),
  "slide must contain numbered badge label",
);
assert.match(
  slideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.primary}"/>`),
  "architecture node badge must use BorekColors.primary",
);
assert.match(slideXml, /ellipse|prst="ellipse"/, "slide must include numbered badge ellipse");
assert.match(slideXml, /roundRect|prst="roundRect"/, "slide must include content card shape");

process.stdout.write("AT-29 renderer unit checks passed\n");
