/** BT-19 focused renderer tests. */

import assert from "node:assert/strict";

import type { ProblemSolution01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_a_problem_solution_01.js";
import minimalFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_a/problem_solution_01.minimal.json";
import realisticFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_a/problem_solution_01.realistic.json";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import {
  computeProblemSolution01Layout,
  renderProblemSolution01,
} from "./renderProblemSolution01.js";
import {
  assertRendererUsesSharedPrimitives,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "./rendererTestHelpers.js";

const minimalFixture = minimalFixtureJson as ProblemSolution01SlideSpec;
const realisticFixture = realisticFixtureJson as ProblemSolution01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderProblemSolution01.ts", import.meta.url));

assertRendererUsesSharedPrimitives(rendererSource, 2);

const noSubtitleLayout = computeProblemSolution01Layout(false);
const subtitleLayout = computeProblemSolution01Layout(true);
assert.deepEqual(
  computeProblemSolution01Layout(true),
  subtitleLayout,
  "layout must be deterministic",
);
assert.equal(noSubtitleLayout.subtitle, undefined);
assert.ok(subtitleLayout.subtitle);
assert.equal(subtitleLayout.problem.y, subtitleLayout.solution.y);
assert.equal(subtitleLayout.problem.w, subtitleLayout.solution.w);
assert.ok(
  Math.abs(
    subtitleLayout.solution.x -
      (subtitleLayout.problem.x + subtitleLayout.problem.w) -
      BorekGrid.columnGap,
  ) < Number.EPSILON * 2,
);
assert.equal(subtitleLayout.problem.x, BorekSpacing.marginX);

for (const fixture of [minimalFixture, realisticFixture]) {
  const original = structuredClone(fixture);
  const first = await renderToPptx((pptx) => renderProblemSolution01(pptx, fixture));
  const second = await renderToPptx((pptx) => renderProblemSolution01(pptx, fixture));
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
  ]);
}

const maximumFixture: ProblemSolution01SlideSpec = {
  ...structuredClone(realisticFixture),
  sectionLabel: "LÖSUNG & KONTROLLE".padEnd(32, "X"),
  title: "Problem und Lösung für geprüfte Abläufe ".padEnd(72, "Y"),
  subtitle: "Human control & deterministic automation ".padEnd(100, "Z"),
  problem: { title: "Manuelle Prüfung ".padEnd(48, "P"), description: "Ü".repeat(220) },
  solution: { title: "Automated standard case ".padEnd(48, "S"), description: "B".repeat(220) },
};
const maximum = await renderToPptx((pptx) => renderProblemSolution01(pptx, maximumFixture));
assertXmlContains(maximum.slideXml, [maximumFixture.title, "Ü".repeat(220), "&amp;"]);

process.stdout.write("BT-19 PROBLEM_SOLUTION_01 renderer checks passed\n");
