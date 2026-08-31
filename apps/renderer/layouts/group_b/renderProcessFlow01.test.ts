/** JJ-15 focused renderer tests. */

import assert from "node:assert/strict";

import type { ProcessFlow01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_b_process_flow_01.js";
import minimalFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_b/process_flow_01.minimal.json";
import realisticFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_b/process_flow_01.realistic.json";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import {
  computeProcessFlow01Layout,
  processFlowRowSizes,
  renderProcessFlow01,
} from "./renderProcessFlow01.js";
import {
  assertNoInlineDesignTokens,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "../rendererTestHelpers.js";
import { JJ20_ENGLISH, JJ20_GERMAN, JJ20_SPECIAL, padTo, xmlForAssert } from "./jj20Coverage.js";

const minimalFixture = minimalFixtureJson as ProcessFlow01SlideSpec;
const realisticFixture = realisticFixtureJson as ProcessFlow01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderProcessFlow01.ts", import.meta.url));

assert.match(rendererSource, /MASTER_CONTENT_NAME/);
assert.match(rendererSource, /addSlideTitle\(/);
assert.match(rendererSource, /addSectionLabel\(/);
assert.match(rendererSource, /addProcessStep\(/);
assert.match(rendererSource, /addConnector\(/);
assertNoInlineDesignTokens(rendererSource);

assert.deepEqual(processFlowRowSizes(1), [1]);
assert.deepEqual(processFlowRowSizes(4), [4]);
assert.deepEqual(processFlowRowSizes(5), [3, 2]);
assert.deepEqual(processFlowRowSizes(8), [4, 4]);

const noSubtitleLayout = computeProcessFlow01Layout(false, 1);
const fiveLayout = computeProcessFlow01Layout(true, 5);
assert.deepEqual(computeProcessFlow01Layout(true, 5), fiveLayout, "layout must be deterministic");
assert.equal(noSubtitleLayout.subtitle, undefined);
assert.ok(fiveLayout.subtitle);
assert.equal(fiveLayout.rows.length, 2);
assert.equal(fiveLayout.cards.length, 5);
assert.equal(fiveLayout.cards[0]?.x, BorekSpacing.marginX);
assert.ok(
  Math.abs(
    fiveLayout.rows[0]![1]!.x -
      (fiveLayout.rows[0]![0]!.x + fiveLayout.rows[0]![0]!.w) -
      BorekGrid.columnGap,
  ) < 1e-9,
);

for (const fixture of [minimalFixture, realisticFixture]) {
  const original = structuredClone(fixture);
  const first = await renderToPptx((pptx) => renderProcessFlow01(pptx, fixture));
  const second = await renderToPptx((pptx) => renderProcessFlow01(pptx, fixture));
  assert.deepEqual(fixture, original, "renderer must not mutate its SlideSpec");
  assert.equal(first.slideXml, second.slideXml, "same SlideSpec must produce deterministic slide XML");
  assertXmlContains(first.slideXml, [
    ...(fixture.sectionLabel ? [fixture.sectionLabel] : []),
    fixture.title,
    ...(fixture.subtitle ? [fixture.subtitle] : []),
    ...fixture.phases.flatMap((phase) => [phase.name, phase.description, String(phase.number)]),
  ]);
}

const maximumFixture: ProcessFlow01SlideSpec = {
  schema_version: "1.0",
  layoutId: "PROCESS_FLOW_01",
  sectionLabel: "PROZESS & FLOW".padEnd(32, "Ä"),
  title: "From mailbox to posting für geprüfte Abläufe ".padEnd(72, "Ü"),
  subtitle: "Confirmed standard case & human-controlled exceptions ".padEnd(100, "ß"),
  sourceChapterIds: ["2", "4"],
  phases: Array.from({ length: 8 }, (_, index) => ({
    number: index + 1,
    name: `Phase ${index + 1} Prüfung `.padEnd(32, String(index + 1)),
    description: `Deutsch & English step ${index + 1} `.padEnd(80, "X"),
  })),
};
const maximum = await renderToPptx((pptx) => renderProcessFlow01(pptx, maximumFixture));
assert.equal(computeProcessFlow01Layout(true, 8).cards.length, 8);
assertXmlContains(maximum.slideXml, [
  maximumFixture.title,
  maximumFixture.phases[7]!.name,
  maximumFixture.phases[7]!.description.replace("&", "&amp;"),
  "&amp;",
  "Ä",
]);

const englishFixture: ProcessFlow01SlideSpec = {
  schema_version: "1.0",
  layoutId: "PROCESS_FLOW_01",
  title: JJ20_ENGLISH,
  sourceChapterIds: ["2"],
  phases: [{ number: 1, name: "Receive invoice", description: "Mailbox intake stays read-only" }],
};
const germanFixture: ProcessFlow01SlideSpec = {
  schema_version: "1.0",
  layoutId: "PROCESS_FLOW_01",
  title: JJ20_GERMAN,
  sourceChapterIds: ["2"],
  phases: [
    { number: 1, name: "Rechnung empfangen", description: "Posteingang bleibt schreibgeschützt" },
  ],
};
const specialLongFixture: ProcessFlow01SlideSpec = {
  schema_version: "1.0",
  layoutId: "PROCESS_FLOW_01",
  title: padTo(`${JJ20_SPECIAL} flow `, 72),
  sourceChapterIds: ["2"],
  phases: [
    {
      number: 1,
      name: padTo(`${JJ20_SPECIAL} `, 32),
      description: padTo("Deutsch & English exception path ", 80),
    },
  ],
};

const english = await renderToPptx((pptx) => renderProcessFlow01(pptx, englishFixture));
const german = await renderToPptx((pptx) => renderProcessFlow01(pptx, germanFixture));
const specialLong = await renderToPptx((pptx) => renderProcessFlow01(pptx, specialLongFixture));
assertXmlContains(english.slideXml, [JJ20_ENGLISH, "Receive invoice"]);
assertXmlContains(german.slideXml, [JJ20_GERMAN, "Rechnung empfangen"]);
assert.equal(specialLongFixture.title.length, 72);
assert.equal(specialLongFixture.phases[0]!.name.length, 32);
assertXmlContains(specialLong.slideXml, [xmlForAssert(JJ20_SPECIAL), "&amp;", "Ä"]);

process.stdout.write("JJ-15 PROCESS_FLOW_01 renderer checks passed\n");
