/** BT-20 focused renderer tests. */

import assert from "node:assert/strict";

import type { Scope01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_a_scope_01.js";
import minimalFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_a/scope_01.minimal.json";
import realisticFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_a/scope_01.realistic.json";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { computeScope01Layout, renderScope01 } from "./renderScope01.js";
import {
  HARDCODED_HEX_PATTERN,
  INLINE_FONT_FAMILY_PATTERN,
  INLINE_FONT_SIZE_PATTERN,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "./rendererTestHelpers.js";

const minimalFixture = minimalFixtureJson as Scope01SlideSpec;
const realisticFixture = realisticFixtureJson as Scope01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderScope01.ts", import.meta.url));

assert.match(rendererSource, /MASTER_CONTENT_NAME/);
assert.match(rendererSource, /addSlideTitle\(/);
assert.match(rendererSource, /addSectionLabel\(/);
assert.match(rendererSource, /addBulletList\(/);
assert.match(rendererSource, /BorekBorders\.divider/);
assert.deepEqual([...rendererSource.matchAll(HARDCODED_HEX_PATTERN)], []);
assert.deepEqual([...rendererSource.matchAll(INLINE_FONT_SIZE_PATTERN)], []);
assert.deepEqual([...rendererSource.matchAll(INLINE_FONT_FAMILY_PATTERN)], []);
assert.doesNotMatch(rendererSource, /\b(?:fetch|axios|OpenAI)\b/);

const noSubtitleLayout = computeScope01Layout(false);
const subtitleLayout = computeScope01Layout(true);
assert.deepEqual(computeScope01Layout(true), subtitleLayout, "layout must be deterministic");
assert.equal(noSubtitleLayout.subtitle, undefined);
assert.ok(subtitleLayout.subtitle);
assert.equal(subtitleLayout.included.label.y, subtitleLayout.later.label.y);
assert.ok(subtitleLayout.included.label.w > subtitleLayout.later.label.w);
assert.equal(subtitleLayout.included.label.x, BorekSpacing.marginX);
assert.ok(
  Math.abs(
    subtitleLayout.later.label.x -
      (subtitleLayout.included.label.x + subtitleLayout.included.label.w) -
      BorekGrid.columnGap,
  ) < Number.EPSILON * 2,
);

for (const fixture of [minimalFixture, realisticFixture]) {
  const original = structuredClone(fixture);
  const first = await renderToPptx((pptx) => renderScope01(pptx, fixture));
  const second = await renderToPptx((pptx) => renderScope01(pptx, fixture));
  assert.deepEqual(fixture, original, "renderer must not mutate its SlideSpec");
  assert.equal(first.slideXml, second.slideXml, "same SlideSpec must produce deterministic slide XML");
  assertXmlContains(first.slideXml, [
    ...(fixture.sectionLabel ? [fixture.sectionLabel] : []),
    fixture.title,
    ...(fixture.subtitle ? [fixture.subtitle] : []),
    "Included",
    "Later",
    ...fixture.included,
    ...fixture.later,
  ]);
}

const maximumFixture: Scope01SlideSpec = {
  schema_version: "1.0",
  layoutId: "SCOPE_01",
  sectionLabel: "SCOPE & UMFANG".padEnd(32, "Ä"),
  title: "Scope für kontrollierte Automatisierung ".padEnd(72, "Ü"),
  subtitle: "Included now & deliberately planned for later ".padEnd(100, "ß"),
  sourceChapterIds: ["3", "5"],
  included: Array.from({ length: 7 }, (_, index) =>
    `Enthalten ${index + 1}: Deutsch & English `.padEnd(72, String(index + 1)),
  ),
  later: Array.from({ length: 5 }, (_, index) =>
    `Später ${index + 1}: geprüft & geplant `.padEnd(72, String(index + 1)),
  ),
};
const maximum = await renderToPptx((pptx) => renderScope01(pptx, maximumFixture));
assertXmlContains(maximum.slideXml, [
  maximumFixture.title,
  maximumFixture.included[6].replace("&", "&amp;"),
  "&amp;",
  "Ä",
]);

process.stdout.write("BT-20 SCOPE_01 renderer checks passed\n");
