/** JJ-16 focused renderer tests. */

import assert from "node:assert/strict";

import type { Timeline01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_b_timeline_01.js";
import minimalFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_b/timeline_01.minimal.json";
import realisticFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_b/timeline_01.realistic.json";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import {
  buildTimeline01PhaseItems,
  computeTimeline01Layout,
  parseTimelineDateRange,
  renderTimeline01,
} from "./renderTimeline01.js";
import {
  assertNoInlineDesignTokens,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "../rendererTestHelpers.js";
import { JJ20_ENGLISH, JJ20_GERMAN, JJ20_SPECIAL, padTo, xmlForAssert } from "./jj20Coverage.js";

const minimalFixture = minimalFixtureJson as Timeline01SlideSpec;
const realisticFixture = realisticFixtureJson as Timeline01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderTimeline01.ts", import.meta.url));

assert.match(rendererSource, /MASTER_CONTENT_NAME/);
assert.match(rendererSource, /addSlideTitle\(/);
assert.match(rendererSource, /addSectionLabel\(/);
assert.match(rendererSource, /addTimeline\(/);
assert.match(rendererSource, /addMilestone\(/);
assertNoInlineDesignTokens(rendererSource);

assert.deepEqual(parseTimelineDateRange("Week 2"), { start: 2, end: 2, kind: "week" });
assert.deepEqual(parseTimelineDateRange("Week 2 to Week 8"), {
  start: 2,
  end: 8,
  kind: "week",
});
assert.equal(parseTimelineDateRange("Week 8 to Week 2"), null);

const weekItems = buildTimeline01PhaseItems(realisticFixture.phases, realisticFixture.milestones);
assert.deepEqual(
  weekItems.map((phase) => phase.positionStart),
  [0, 2, 6, 10],
);
assert.deepEqual(
  weekItems.map((phase) => phase.positionEnd),
  [2, 6, 10, 14],
);

const layout = computeTimeline01Layout(true, weekItems, realisticFixture.milestones.length);
assert.deepEqual(
  computeTimeline01Layout(true, weekItems, realisticFixture.milestones.length),
  layout,
  "layout must be deterministic",
);
assert.ok(layout.subtitle);
assert.equal(layout.timeline.x, BorekSpacing.marginX);
assert.equal(layout.milestoneAnchors.length, 4);
assert.ok(layout.milestoneAnchors[0]!.x < layout.milestoneAnchors[3]!.x);
assert.equal(layout.milestoneAnchors[0]!.y, layout.milestoneAnchors[3]!.y);

for (const fixture of [minimalFixture, realisticFixture]) {
  const original = structuredClone(fixture);
  const first = await renderToPptx((pptx) => renderTimeline01(pptx, fixture));
  const second = await renderToPptx((pptx) => renderTimeline01(pptx, fixture));
  assert.deepEqual(fixture, original, "renderer must not mutate its SlideSpec");
  assert.equal(first.slideXml, second.slideXml, "same SlideSpec must produce deterministic slide XML");
  assertXmlContains(first.slideXml, [
    ...(fixture.sectionLabel ? [fixture.sectionLabel] : []),
    fixture.title,
    ...(fixture.subtitle ? [fixture.subtitle] : []),
    ...fixture.phases.flatMap((phase) => [phase.name, phase.description]),
    ...fixture.milestones.map((milestone) => milestone.name),
    ...fixture.milestones.flatMap((milestone) => (milestone.date ? [milestone.date] : [])),
  ]);
}

const maximumFixture: Timeline01SlideSpec = {
  schema_version: "1.0",
  layoutId: "TIMELINE_01",
  sectionLabel: "ZEITPLAN & PILOT".padEnd(32, "Ä"),
  title: "Implementation roadmap für geprüfte Abläufe ".padEnd(72, "Ü"),
  subtitle: "Phases & checkpoints stay aligned on one dual-band slide ".padEnd(100, "ß"),
  sourceChapterIds: ["10"],
  phases: Array.from({ length: 8 }, (_, index) => ({
    id: `p${index + 1}`,
    name: `Phase ${index + 1} `.padEnd(28, "P"),
    description: `Deutsch & English ${index + 1} `.padEnd(75, "D"),
  })),
  milestones: Array.from({ length: 8 }, (_, index) => ({
    id: `m${index + 1}`,
    name: `Gate ${index + 1} Prüfung `.padEnd(32, "G"),
    phaseId: `p${index + 1}`,
    date: `Week ${(index + 1) * 2}`,
    description: `Checkpoint ${index + 1} & review `.padEnd(80, "C"),
  })),
};
const maximum = await renderToPptx((pptx) => renderTimeline01(pptx, maximumFixture));
assertXmlContains(maximum.slideXml, [
  maximumFixture.title,
  maximumFixture.phases[7]!.name,
  maximumFixture.milestones[7]!.name,
  "Week 16",
  "&amp;",
  "Ä",
]);

const englishFixture: Timeline01SlideSpec = {
  schema_version: "1.0",
  layoutId: "TIMELINE_01",
  title: JJ20_ENGLISH,
  sourceChapterIds: ["10"],
  phases: [{ id: "p1", name: "Discover", description: "Confirm scope and access" }],
  milestones: [{ id: "m1", name: "Access confirmed", phaseId: "p1", date: "Week 2" }],
};
const germanFixture: Timeline01SlideSpec = {
  schema_version: "1.0",
  layoutId: "TIMELINE_01",
  title: JJ20_GERMAN,
  sourceChapterIds: ["10"],
  phases: [{ id: "p1", name: "Entdecken", description: "Umfang und Zugang bestätigen" }],
  milestones: [{ id: "m1", name: "Zugang bestätigt", phaseId: "p1", date: "Woche 2" }],
};
const specialLongFixture: Timeline01SlideSpec = {
  schema_version: "1.0",
  layoutId: "TIMELINE_01",
  title: padTo(`${JJ20_SPECIAL} roadmap `, 72),
  sourceChapterIds: ["10"],
  phases: [
    {
      id: "p1",
      name: padTo("Long phase name ", 28),
      description: padTo("Deutsch & English overlap ", 75),
    },
  ],
  milestones: [
    {
      id: "m1",
      name: padTo(`${JJ20_SPECIAL} `, 32),
      phaseId: "p1",
      date: "Week 2 to Week 8",
    },
  ],
};

const english = await renderToPptx((pptx) => renderTimeline01(pptx, englishFixture));
const german = await renderToPptx((pptx) => renderTimeline01(pptx, germanFixture));
const specialLong = await renderToPptx((pptx) => renderTimeline01(pptx, specialLongFixture));
assertXmlContains(english.slideXml, [JJ20_ENGLISH, "Discover", "Access confirmed"]);
assertXmlContains(german.slideXml, [JJ20_GERMAN, "Entdecken", "Zugang bestätigt"]);
assert.equal(specialLongFixture.title.length, 72);
assert.equal(specialLongFixture.phases[0]!.name.length, 28);
assertXmlContains(specialLong.slideXml, [xmlForAssert(JJ20_SPECIAL), "&amp;", "Ä"]);

process.stdout.write("JJ-16 TIMELINE_01 renderer checks passed\n");
