/** JJ-21: TIMELINE_01 edge cases — single phase, maximum phases, overlapping date ranges. */

import assert from "node:assert/strict";

import type { Timeline01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_b_timeline_01.js";
import minimalFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_b/timeline_01.minimal.json";
import {
  computeTimelineLayout,
  timelinePhasesOverlap,
} from "../../design_system/components/addTimeline.js";
import {
  buildTimeline01PhaseItems,
  computeTimeline01Layout,
  parseTimelineDateRange,
  renderTimeline01,
} from "./renderTimeline01.js";
import { assertXmlContains, renderToPptx } from "../rendererTestHelpers.js";

const minimalFixture = minimalFixtureJson as Timeline01SlideSpec;

const singlePhase = await renderToPptx((pptx) => renderTimeline01(pptx, minimalFixture));
assertXmlContains(singlePhase.slideXml, [
  minimalFixture.title,
  minimalFixture.phases[0]!.name,
  minimalFixture.milestones[0]!.name,
]);
const singleItems = buildTimeline01PhaseItems(minimalFixture.phases, minimalFixture.milestones);
assert.equal(singleItems.length, 1);
const singleLayout = computeTimeline01Layout(false, singleItems, 1);
assert.equal(singleLayout.milestoneAnchors.length, 1);
assert.equal(computeTimelineLayout(singleLayout.timeline, singleItems).phases.length, 1);

const maximumFixture: Timeline01SlideSpec = {
  schema_version: "1.0",
  layoutId: "TIMELINE_01",
  title: "Maximum phase roadmap",
  sourceChapterIds: ["10"],
  phases: Array.from({ length: 8 }, (_, index) => ({
    id: `p${index + 1}`,
    name: `Phase ${index + 1}`,
    description: `Workstream ${index + 1}`,
  })),
  milestones: Array.from({ length: 8 }, (_, index) => ({
    id: `m${index + 1}`,
    name: `Gate ${index + 1}`,
    phaseId: `p${index + 1}`,
    date: `Week ${(index + 1) * 2}`,
  })),
};
const maximumItems = buildTimeline01PhaseItems(maximumFixture.phases, maximumFixture.milestones);
assert.equal(maximumItems.length, 8);
assert.deepEqual(
  maximumItems.map((phase) => phase.positionEnd),
  [2, 4, 6, 8, 10, 12, 14, 16],
);
assert.equal(
  timelinePhasesOverlap(
    maximumItems.map((phase) => ({
      start: phase.positionStart!,
      end: phase.positionEnd!,
    })),
  ),
  false,
);
const maximumRendered = await renderToPptx((pptx) => renderTimeline01(pptx, maximumFixture));
assertXmlContains(maximumRendered.slideXml, [
  "Phase 1",
  "Phase 8",
  "Gate 1",
  "Gate 8",
  "Week 2",
  "Week 16",
]);

const overlappingFixture: Timeline01SlideSpec = {
  schema_version: "1.0",
  layoutId: "TIMELINE_01",
  title: "Overlapping workstreams",
  subtitle: "Build and pilot run in parallel",
  sourceChapterIds: ["10"],
  phases: [
    { id: "p1", name: "Build", description: "Matching rules and ERP write path" },
    { id: "p2", name: "Pilot", description: "Controlled live invoice sample" },
    { id: "p3", name: "Handover", description: "Operations take ownership" },
  ],
  milestones: [
    { id: "m1", name: "Rules ready", phaseId: "p1", date: "Week 2 to Week 10" },
    { id: "m2", name: "Pilot window", phaseId: "p2", date: "Week 6 to Week 12" },
    { id: "m3", name: "Runbook accepted", phaseId: "p3", date: "Week 10 to Week 14" },
  ],
};

assert.deepEqual(parseTimelineDateRange("Week 2 to Week 10"), {
  start: 2,
  end: 10,
  kind: "week",
});
assert.deepEqual(parseTimelineDateRange("2026-01-15 to 2026-04-01"), {
  start: Date.parse("2026-01-15T00:00:00Z") / 86_400_000,
  end: Date.parse("2026-04-01T00:00:00Z") / 86_400_000,
  kind: "day",
});

const overlappingItems = buildTimeline01PhaseItems(
  overlappingFixture.phases,
  overlappingFixture.milestones,
);
assert.deepEqual(
  overlappingItems.map((phase) => [phase.positionStart, phase.positionEnd]),
  [
    [2, 10],
    [6, 12],
    [10, 14],
  ],
);
assert.equal(
  timelinePhasesOverlap(
    overlappingItems.map((phase) => ({
      start: phase.positionStart!,
      end: phase.positionEnd!,
    })),
  ),
  true,
);

const overlappingLayout = computeTimeline01Layout(true, overlappingItems, 3);
const overlappingGeometry = computeTimelineLayout(
  overlappingLayout.timeline,
  overlappingItems,
);
const buildSegment = overlappingGeometry.phases[0]!;
const pilotSegment = overlappingGeometry.phases[1]!;
assert.ok(
  pilotSegment.segment.x < buildSegment.segment.x + buildSegment.segment.w,
  "overlapping date ranges must share horizontal track space",
);
assert.ok(pilotSegment.segment.x > buildSegment.segment.x);
assert.equal(
  Number(overlappingLayout.milestoneAnchors[0]!.x.toFixed(4)),
  Number((buildSegment.segment.x + buildSegment.segment.w).toFixed(4)),
  "JJ-22: overlapping phases still park the phase checkpoint on the end tick",
);

const overlappingRendered = await renderToPptx((pptx) =>
  renderTimeline01(pptx, overlappingFixture),
);
assertXmlContains(overlappingRendered.slideXml, [
  overlappingFixture.title,
  "Build",
  "Pilot",
  "Handover",
  "Rules ready",
  "Pilot window",
  "Week 2 to Week 10",
  "Week 6 to Week 12",
]);

const isoOverlapFixture: Timeline01SlideSpec = {
  schema_version: "1.0",
  layoutId: "TIMELINE_01",
  title: "Calendar overlap",
  sourceChapterIds: ["10"],
  phases: [
    { id: "p1", name: "Discover", description: "Confirm scope and access" },
    { id: "p2", name: "Build", description: "Matching rules" },
  ],
  milestones: [
    { id: "m1", name: "Access", phaseId: "p1", date: "2026-01-01 to 2026-03-31" },
    { id: "m2", name: "Rules", phaseId: "p2", date: "2026-02-15 to 2026-05-01" },
  ],
};
const isoItems = buildTimeline01PhaseItems(isoOverlapFixture.phases, isoOverlapFixture.milestones);
assert.equal(isoItems[0]?.positionStart! < isoItems[1]?.positionStart!, true);
assert.equal(isoItems[0]?.positionEnd! > isoItems[1]?.positionStart!, true);
const isoRendered = await renderToPptx((pptx) => renderTimeline01(pptx, isoOverlapFixture));
assertXmlContains(isoRendered.slideXml, ["Discover", "Build", "Access", "Rules"]);

process.stdout.write("JJ-21 TIMELINE_01 edge-case checks passed\n");
