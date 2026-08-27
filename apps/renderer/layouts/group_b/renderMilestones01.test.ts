/** JJ-17 focused renderer tests. */

import assert from "node:assert/strict";

import type { Milestones01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_b_milestones_01.js";
import minimalFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_b/milestones_01.minimal.json";
import realisticFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_b/milestones_01.realistic.json";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { computeMilestones01Layout, renderMilestones01 } from "./renderMilestones01.js";
import {
  assertNoInlineDesignTokens,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "../rendererTestHelpers.js";

const minimalFixture = minimalFixtureJson as Milestones01SlideSpec;
const realisticFixture = realisticFixtureJson as Milestones01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderMilestones01.ts", import.meta.url));

assert.match(rendererSource, /MASTER_CONTENT_NAME/);
assert.match(rendererSource, /addSlideTitle\(/);
assert.match(rendererSource, /addSectionLabel\(/);
assert.match(rendererSource, /addMilestone\(/);
assert.match(rendererSource, /addConnector\(/);
assert.match(rendererSource, /addContentCard\(/);
assertNoInlineDesignTokens(rendererSource);

const noSubtitleLayout = computeMilestones01Layout(false, 1);
const datedLayout = computeMilestones01Layout(true, 4, [
  "Week 2",
  "Week 6",
  "Week 10",
  "Week 14",
]);
assert.deepEqual(
  computeMilestones01Layout(true, 4, ["Week 2", "Week 6", "Week 10", "Week 14"]),
  datedLayout,
  "layout must be deterministic",
);
assert.equal(noSubtitleLayout.subtitle, undefined);
assert.ok(datedLayout.subtitle);
assert.equal(datedLayout.anchors.length, 4);
assert.equal(datedLayout.descriptions.length, 4);
assert.equal(datedLayout.trackFrom.y, datedLayout.trackTo.y);
assert.equal(datedLayout.trackFrom.x > BorekSpacing.marginX, true);
assert.ok(datedLayout.anchors[0]!.x < datedLayout.anchors[3]!.x);
assert.ok(
  Math.abs(
    (datedLayout.anchors[1]!.x - datedLayout.anchors[0]!.x) -
      (datedLayout.anchors[2]!.x - datedLayout.anchors[1]!.x),
  ) < 1e-9,
);

for (const fixture of [minimalFixture, realisticFixture]) {
  const original = structuredClone(fixture);
  const first = await renderToPptx((pptx) => renderMilestones01(pptx, fixture));
  const second = await renderToPptx((pptx) => renderMilestones01(pptx, fixture));
  assert.deepEqual(fixture, original, "renderer must not mutate its SlideSpec");
  assert.equal(first.slideXml, second.slideXml, "same SlideSpec must produce deterministic slide XML");
  assertXmlContains(first.slideXml, [
    ...(fixture.sectionLabel ? [fixture.sectionLabel] : []),
    fixture.title,
    ...(fixture.subtitle ? [fixture.subtitle] : []),
    ...fixture.milestones.flatMap((milestone) => [
      milestone.name,
      milestone.description,
      ...(milestone.date ? [milestone.date] : []),
    ]),
  ]);
}

const maximumFixture: Milestones01SlideSpec = {
  schema_version: "1.0",
  layoutId: "MILESTONES_01",
  sectionLabel: "MEILENSTEINE & PILOT".padEnd(32, "Ä"),
  title: "Delivery checkpoints für geprüfte Abläufe ".padEnd(72, "Ü"),
  subtitle: "Standalone list & dual-band timeline stay independent ".padEnd(100, "ß"),
  sourceChapterIds: ["10"],
  milestones: Array.from({ length: 8 }, (_, index) => ({
    name: `Checkpoint ${index + 1} Prüfung `.padEnd(40, "N"),
    description: `Deutsch & English gate ${index + 1} `.padEnd(90, "D"),
    date: `Week ${(index + 1) * 2}`,
  })),
};
const maximum = await renderToPptx((pptx) => renderMilestones01(pptx, maximumFixture));
assert.equal(computeMilestones01Layout(true, 8).anchors.length, 8);
assertXmlContains(maximum.slideXml, [
  maximumFixture.title,
  maximumFixture.milestones[7]!.name,
  maximumFixture.milestones[7]!.description.replace("&", "&amp;"),
  "Week 16",
  "&amp;",
  "Ä",
]);

process.stdout.write("JJ-17 MILESTONES_01 renderer checks passed\n");
