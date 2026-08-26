/** BT-18 focused renderer tests. */

import assert from "node:assert/strict";

import type { Context01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_a_context_01.js";
import minimalFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_a/context_01.minimal.json";
import realisticFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_a/context_01.realistic.json";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { computeContext01Layout, renderContext01 } from "./renderContext01.js";
import {
  assertRendererUsesSharedPrimitives,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "./rendererTestHelpers.js";

const minimalFixture = minimalFixtureJson as Context01SlideSpec;
const realisticFixture = realisticFixtureJson as Context01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderContext01.ts", import.meta.url));

assertRendererUsesSharedPrimitives(rendererSource, 4);

const noSubtitleLayout = computeContext01Layout(false);
const subtitleLayout = computeContext01Layout(true);
assert.deepEqual(computeContext01Layout(true), subtitleLayout, "layout must be deterministic");
assert.equal(noSubtitleLayout.subtitle, undefined);
assert.ok(subtitleLayout.subtitle);
assert.equal(subtitleLayout.problem.x, subtitleLayout.currentState.x);
assert.equal(subtitleLayout.solution.x, subtitleLayout.targetState.x);
assert.ok(
  Math.abs(
    subtitleLayout.solution.x -
      (subtitleLayout.problem.x + subtitleLayout.problem.w) -
      BorekGrid.columnGap,
  ) < Number.EPSILON * 2,
);
assert.ok(
  Math.abs(
    subtitleLayout.currentState.y -
      (subtitleLayout.problem.y + subtitleLayout.problem.h) -
      BorekGrid.rowGap,
  ) < Number.EPSILON * 2,
);
assert.equal(subtitleLayout.problem.x, BorekSpacing.marginX);

for (const fixture of [minimalFixture, realisticFixture]) {
  const original = structuredClone(fixture);
  const first = await renderToPptx((pptx) => renderContext01(pptx, fixture));
  const second = await renderToPptx((pptx) => renderContext01(pptx, fixture));
  assert.deepEqual(fixture, original, "renderer must not mutate its SlideSpec");
  assert.equal(first.slideXml, second.slideXml, "same SlideSpec must produce deterministic slide XML");
  assertXmlContains(first.slideXml, [
    ...(fixture.sectionLabel ? [fixture.sectionLabel] : []),
    fixture.title,
    ...(fixture.subtitle ? [fixture.subtitle] : []),
    fixture.problem.title,
    fixture.problem.description,
    fixture.solution.title,
    fixture.solution.description,
    fixture.currentState.title,
    fixture.currentState.description,
    fixture.targetState.title,
    fixture.targetState.description,
  ]);
}

const maximumFixture: Context01SlideSpec = {
  ...structuredClone(realisticFixture),
  sectionLabel: "K".repeat(32),
  title: "Kontext und Übergang ".padEnd(72, "X"),
  subtitle: "Controlled automation & menschliche Prüfung ".padEnd(100, "Y"),
  problem: { title: "Problem ".padEnd(32, "P"), description: "Ä".repeat(160) },
  solution: { title: "Solution ".padEnd(32, "S"), description: "B".repeat(160) },
  currentState: { title: "Ist-Zustand ".padEnd(32, "I"), description: "C".repeat(160) },
  targetState: { title: "Target state ".padEnd(32, "T"), description: "D".repeat(160) },
};
const maximum = await renderToPptx((pptx) => renderContext01(pptx, maximumFixture));
assertXmlContains(maximum.slideXml, [maximumFixture.title, "Ä".repeat(160), "&amp;"]);

process.stdout.write("BT-18 CONTEXT_01 renderer checks passed\n");
