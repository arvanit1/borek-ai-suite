/** AT-32 unit checks executed by pytest via `npm run test:at32 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  MILESTONE_MARKER_SHAPE,
  addMilestone,
  computeMilestoneLayout,
  milestoneBandGap,
  milestoneLabelBandHeight,
  milestoneLabelWidth,
  milestoneMarkerDiameter,
  milestoneMarkerShapeOptions,
} from "./addMilestone.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
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

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addMilestone.ts");

const ANCHOR = { x: 5.0, y: 4.2 };
const LABEL_ONLY = { label: "Pilot go-live" };
const LABEL_AND_DATE = { label: "Pilot go-live", date: "Week 10" };

assert.ok(existsSync(COMPONENT_TS), "addMilestone.ts must exist");
assert.equal(MILESTONE_MARKER_SHAPE, "diamond");
assert.equal(milestoneMarkerDiameter(), BorekGrid.rowGap * 2);
assert.equal(milestoneLabelWidth(), milestoneMarkerDiameter() * 6);
assert.equal(milestoneLabelBandHeight(), BorekSpacing.footerHeight);
assert.equal(milestoneBandGap(), BorekGrid.rowGap);

const layoutNoDate = computeMilestoneLayout(ANCHOR, LABEL_ONLY);
const half = milestoneMarkerDiameter() / 2;
assert.equal(layoutNoDate.marker.x, ANCHOR.x - half);
assert.equal(layoutNoDate.marker.y, ANCHOR.y - half);
assert.equal(layoutNoDate.marker.w, milestoneMarkerDiameter());
assert.equal(layoutNoDate.marker.h, milestoneMarkerDiameter());
assert.equal(layoutNoDate.label.y, ANCHOR.y + half + milestoneBandGap());
assert.equal(layoutNoDate.date, undefined);

const layoutWithDate = computeMilestoneLayout(ANCHOR, LABEL_AND_DATE);
assert.ok(layoutWithDate.date);
assert.equal(
  layoutWithDate.date!.y,
  layoutWithDate.label.y + milestoneLabelBandHeight() + milestoneBandGap(),
);

const markerOptions = milestoneMarkerShapeOptions(layoutNoDate.marker);
assert.equal(markerOptions.fill.color, BorekColors.primary);

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

function renderMilestone(milestone: { label: string; date?: string }) {
  const pptx = new PptxGenJS();
  registerMasterContent(pptx);
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  addMilestone(slide, ANCHOR, milestone);
  return pptx.write({ outputType: "nodebuffer" });
}

const labelOnlyBuffer = await renderMilestone(LABEL_ONLY);
assert.ok(Buffer.isBuffer(labelOnlyBuffer));

const labelDateBuffer = await renderMilestone(LABEL_AND_DATE);
assert.ok(Buffer.isBuffer(labelDateBuffer));

const zip = await JSZip.loadAsync(labelDateBuffer);
const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
assert.ok(slidePath, "pptx must contain slide1.xml");

const slideXml = await zip.file(slidePath)?.async("string");
assert.ok(slideXml, "slide1.xml must be readable");

assert.match(slideXml, new RegExp(LABEL_AND_DATE.label), "slide must contain milestone label");
assert.match(slideXml, new RegExp(LABEL_AND_DATE.date!), "slide must contain milestone date");
assert.match(
  slideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.primary}"/>`),
  "milestone marker must use BorekColors.primary",
);
assert.match(slideXml, /diamond|prst="diamond"/, "slide must include diamond milestone marker");

process.stdout.write("AT-32 renderer unit checks passed\n");
