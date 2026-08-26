/** AT-28 unit checks executed by pytest via `npm run test:at28 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  TIMELINE_PHASE_SHAPE,
  TIMELINE_TRACK_SHAPE,
  addTimeline,
  buildTimelinePhasesFromSlideSpec,
  computeTimelineLayout,
  computeTimelineScaleEnd,
  parseTimelineWeekLabel,
  resolveTimelinePhasePositions,
  timelineBandGap,
  timelineDateBandHeight,
  timelineDescriptionBandHeight,
  timelinePhaseGap,
  timelinePhaseShapeOptions,
  timelineTrackHeight,
  timelineTrackLineOptions,
} from "./addTimeline.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
import { BorekBorders } from "../tokens/borders.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
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

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addTimeline.ts");

const TIMELINE_RECT = { x: 1.0, y: 2.1, w: 10.0, h: 1.6 };

const SLIDE_SPEC_PHASES = [
  { id: "p1", name: "Discover", description: "Confirm scope, systems and access paths" },
  { id: "p2", name: "Build", description: "Matching rules, exception queue and ERP write path" },
  { id: "p3", name: "Pilot", description: "Controlled run on a live invoice sample" },
  { id: "p4", name: "Handover", description: "Operations take ownership with quality gates" },
];

const SLIDE_SPEC_MILESTONES = [
  { phaseId: "p1", date: "Week 2" },
  { phaseId: "p2", date: "Week 6" },
  { phaseId: "p3", date: "Week 10" },
  { phaseId: "p4", date: "Week 14" },
];

const TIMELINE_CONTENT = {
  phases: buildTimelinePhasesFromSlideSpec(SLIDE_SPEC_PHASES, SLIDE_SPEC_MILESTONES),
};

assert.ok(existsSync(COMPONENT_TS), "addTimeline.ts must exist");
assert.equal(TIMELINE_PHASE_SHAPE, "roundRect");
assert.equal(TIMELINE_TRACK_SHAPE, "line");
assert.equal(parseTimelineWeekLabel("Week 2"), 2);
assert.equal(parseTimelineWeekLabel("week 14"), 14);
assert.equal(parseTimelineWeekLabel("2026-09"), null);

const builtPhases = TIMELINE_CONTENT.phases;
assert.deepEqual(
  builtPhases.map((phase) => phase.positionStart),
  [0, 2, 6, 10],
);
assert.deepEqual(
  builtPhases.map((phase) => phase.positionEnd),
  [2, 6, 10, 14],
);

const positions = resolveTimelinePhasePositions(builtPhases);
assert.equal(computeTimelineScaleEnd(positions), 14);

const layout = computeTimelineLayout(TIMELINE_RECT, builtPhases);
const gap = timelinePhaseGap();
const usableW = TIMELINE_RECT.w - gap * (builtPhases.length - 1);

assert.equal(layout.scaleEnd, 14);
assert.equal(layout.phases[0]?.segment.w, (2 / 14) * usableW);
assert.equal(layout.phases[1]?.segment.w, (4 / 14) * usableW);
assert.equal(layout.phases[0]?.segment.x, TIMELINE_RECT.x);
assert.equal(
  layout.phases[1]?.segment.x,
  TIMELINE_RECT.x + (2 / 14) * usableW + gap,
);

const discoverEndX = layout.phases[0]!.segment.x + layout.phases[0]!.segment.w;
assert.ok(
  Math.abs(layout.phases[0]!.dateLabel.x + layout.phases[0]!.dateLabel.w / 2 - discoverEndX) < 0.001,
  "date label must anchor at the phase end week tick",
);

assert.throws(
  () =>
    resolveTimelinePhasePositions([
      { name: "Bad", positionStart: 4, positionEnd: 2 },
    ]),
  /invalid range/,
);

const shapeOptions = timelinePhaseShapeOptions(layout.phases[0]!.segment);
assert.equal(shapeOptions.fill.color, BorekColors.primary);
assert.equal(shapeOptions.rectRadius, BorekBorders.card.borderRadiusInches);

const trackOptions = timelineTrackLineOptions(layout.track);
assert.equal(trackOptions.line.color, BorekBorders.divider.color);

assert.equal(timelinePhaseGap(), BorekGrid.columnGap);
assert.equal(timelineTrackHeight(), BorekSpacing.footerHeight);
assert.equal(timelineDateBandHeight(), BorekSpacing.footerHeight);
assert.equal(timelineDescriptionBandHeight(), BorekSpacing.footerHeight * 2);
assert.equal(timelineBandGap(), BorekGrid.rowGap);

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

const pptx = new PptxGenJS();
registerMasterContent(pptx);
const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
addTimeline(slide, TIMELINE_RECT, TIMELINE_CONTENT);

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));

const zip = await JSZip.loadAsync(buffer);
const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
assert.ok(slidePath, "pptx must contain slide1.xml");

const slideXml = await zip.file(slidePath)?.async("string");
assert.ok(slideXml, "slide1.xml must be readable");

for (const phase of builtPhases) {
  assert.match(slideXml, new RegExp(phase.name), `slide must contain phase name "${phase.name}"`);
  assert.match(slideXml, new RegExp(phase.dateLabel!), `slide must contain date label "${phase.dateLabel}"`);
}
assert.match(slideXml, /roundRect|prst="roundRect"/, "timeline must include phase segment shapes");
assert.match(
  slideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.primary}"/>`),
  "phase segments must use BorekColors.primary",
);

process.stdout.write("AT-28 renderer unit checks passed\n");
