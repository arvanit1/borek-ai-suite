/** JJ-23 renderer checks for EXECUTIVE_SUMMARY_01. */

import assert from "node:assert/strict";

import type { ExecutiveSummary01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_summary_executive_summary_01.js";
import minimalFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/summary/executive_summary_01.minimal.json" with { type: "json" };
import realisticFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/summary/executive_summary_01.realistic.json" with { type: "json" };
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import {
  computeExecutiveSummary01Layout,
  renderExecutiveSummary01,
} from "./renderExecutiveSummary01.js";
import {
  assertRendererUsesSharedPrimitives,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "../group_a/rendererTestHelpers.js";

const minimalFixture = minimalFixtureJson as ExecutiveSummary01SlideSpec;
const realisticFixture = realisticFixtureJson as ExecutiveSummary01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderExecutiveSummary01.ts", import.meta.url));
const specialName = "Long opportunity ä ö ü Ä Ö Ü ß & / % + (Pilot's) -";

assertRendererUsesSharedPrimitives(rendererSource, 1);
assert.match(rendererSource, /spec\.headline/);

const noSubtitleLayout = computeExecutiveSummary01Layout(false, 3);
const subtitleLayout = computeExecutiveSummary01Layout(true, 4);
assert.deepEqual(computeExecutiveSummary01Layout(true, 4), subtitleLayout, "layout must be deterministic");
assert.equal(noSubtitleLayout.subtitle, undefined);
assert.ok(subtitleLayout.subtitle);
assert.equal(subtitleLayout.highlights.length, 4);
assert.equal(subtitleLayout.highlights[0]?.x, BorekSpacing.marginX);
assert.ok(
  Math.abs(
    subtitleLayout.highlights[1]!.x -
      (subtitleLayout.highlights[0]!.x + subtitleLayout.highlights[0]!.w) -
      BorekGrid.columnGap,
  ) < Number.EPSILON * 8,
);

for (const fixture of [minimalFixture, realisticFixture]) {
  const original = structuredClone(fixture);
  const first = await renderToPptx((pptx) => renderExecutiveSummary01(pptx, fixture));
  const second = await renderToPptx((pptx) => renderExecutiveSummary01(pptx, fixture));
  assert.deepEqual(fixture, original, "renderer must not mutate its SlideSpec");
  assert.equal(first.slideXml, second.slideXml, "same SlideSpec must produce deterministic slide XML");
  assertXmlContains(first.slideXml, [
    ...(fixture.sectionLabel ? [fixture.sectionLabel] : []),
    fixture.title,
    ...(fixture.subtitle ? [fixture.subtitle] : []),
    fixture.headline,
    ...fixture.highlights.flatMap((highlight) => [highlight.title, highlight.description]),
  ]);
}

const maximumFixture: ExecutiveSummary01SlideSpec = {
  ...structuredClone(realisticFixture),
  sectionLabel: "K".repeat(32),
  title: specialName.padEnd(72, "X"),
  subtitle: "Controlled automation & menschliche Prüfung ".padEnd(100, "Y"),
  headline: "Ä".repeat(180),
  highlights: [
    { title: "Problem ".padEnd(32, "P"), description: "A".repeat(140) },
    { title: "Approach ".padEnd(32, "S"), description: "B".repeat(140) },
    { title: "Control ".padEnd(32, "C"), description: "C".repeat(140) },
    { title: "Outcome ".padEnd(32, "O"), description: "D".repeat(140) },
  ],
};
assert.equal(maximumFixture.title.length, 72);
const maximum = await renderToPptx((pptx) => renderExecutiveSummary01(pptx, maximumFixture));
assertXmlContains(maximum.slideXml, [
  specialName.replace("&", "&amp;").replace("'", "&apos;"),
  "Problem",
  "Approach",
]);

process.stdout.write("JJ-23 EXECUTIVE_SUMMARY_01 renderer checks passed\n");
