/** BT-17 renderer checks and BT-23 Group A coverage. */

import assert from "node:assert/strict";

import type { Cover01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_a_cover_01.js";
import minimalFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_a/cover_01.minimal.json";
import realisticFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_a/cover_01.realistic.json";
import {
  computeMasterCoverLayout,
  MASTER_COVER_NAME,
  registerMasterCover,
} from "../../design_system/masters/MASTER_COVER.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { computeCover01BadgeRects, renderCover01 } from "./renderCover01.js";
import {
  HARDCODED_HEX_PATTERN,
  INLINE_FONT_FAMILY_PATTERN,
  INLINE_FONT_SIZE_PATTERN,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "./rendererTestHelpers.js";

const minimalFixture = minimalFixtureJson as Cover01SlideSpec;
const realisticFixture = realisticFixtureJson as Cover01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderCover01.ts", import.meta.url));
const bt23OpportunityName = "Long opportunity ä ö ü Ä Ö Ü ß & / % + (Pilot's) -";
const coverRenderOptions = {
  registerMaster: registerMasterCover,
  expectedMasterName: MASTER_COVER_NAME,
};

assert.match(rendererSource, /MASTER_COVER_NAME/);
assert.match(rendererSource, /addSlideTitle\(/);
assert.match(rendererSource, /addSectionLabel\(/);
assert.match(rendererSource, /addKpiCard\(/);
assert.match(rendererSource, /variant: "inverse"/);
assert.deepEqual([...rendererSource.matchAll(HARDCODED_HEX_PATTERN)], []);
assert.deepEqual([...rendererSource.matchAll(INLINE_FONT_SIZE_PATTERN)], []);
assert.deepEqual([...rendererSource.matchAll(INLINE_FONT_FAMILY_PATTERN)], []);
assert.doesNotMatch(rendererSource, /\b(?:fetch|axios|OpenAI)\b/);

const masterBadgeRects = computeMasterCoverLayout().statBadges;
const expandedBadgeRects = masterBadgeRects.map((rect) => ({
  ...rect,
  y: rect.y - BorekSpacing.footerHeight,
  h: rect.h + BorekSpacing.footerHeight,
}));
assert.deepEqual(computeCover01BadgeRects(1), [expandedBadgeRects[1]]);
assert.deepEqual(computeCover01BadgeRects(2), [expandedBadgeRects[0], expandedBadgeRects[2]]);
assert.deepEqual(computeCover01BadgeRects(3), expandedBadgeRects);
assert.deepEqual(computeCover01BadgeRects(3), computeCover01BadgeRects(3));

for (const fixture of [minimalFixture, realisticFixture]) {
  const original = structuredClone(fixture);
  const first = await renderToPptx((pptx) => renderCover01(pptx, fixture), coverRenderOptions);
  const second = await renderToPptx((pptx) => renderCover01(pptx, fixture), coverRenderOptions);
  assert.deepEqual(fixture, original, "renderer must not mutate its SlideSpec");
  assert.equal(first.slideXml, second.slideXml, "same SlideSpec must produce deterministic slide XML");
  assertXmlContains(first.slideXml, [
    ...(fixture.sectionLabel ? [fixture.sectionLabel] : []),
    fixture.title,
    fixture.subtitle,
    ...fixture.statBadges.flatMap((badge) => [badge.value, badge.label]),
  ]);
}

const twoBadgeFixture: Cover01SlideSpec = {
  schema_version: "1.0",
  layoutId: "COVER_01",
  title: "Controlled automation",
  subtitle: "Two balanced indicators",
  sourceChapterIds: ["1"],
  statBadges: realisticFixture.statBadges.slice(0, 2),
};
const twoBadges = await renderToPptx(
  (pptx) => renderCover01(pptx, twoBadgeFixture),
  coverRenderOptions,
);
assertXmlContains(
  twoBadges.slideXml,
  twoBadgeFixture.statBadges.flatMap((badge) => [badge.value, badge.label]),
);

const maximumFixture: Cover01SlideSpec = {
  schema_version: "1.0",
  layoutId: "COVER_01",
  sectionLabel: "PRÜFUNG & AUTOMATION".padEnd(40, "Ä"),
  title: bt23OpportunityName.padEnd(60, "X"),
  subtitle: "Controlled automation & menschliche Kontrolle ".padEnd(100, "ß"),
  sourceChapterIds: ["1"],
  statBadges: [
    { value: "99,9%", label: "Automatisch geprüft".padEnd(32, "A") },
    { value: "16 Zeichen ABCDE", label: "Human-reviewed exceptions".padEnd(32, "B") },
    { value: "24/7", label: "English & Deutsch".padEnd(32, "C") },
  ],
};
assert.equal(maximumFixture.title.length, 60, "BT-23 cover opportunity name must reach BT-15 max");
const maximum = await renderToPptx(
  (pptx) => renderCover01(pptx, maximumFixture),
  coverRenderOptions,
);
assertXmlContains(maximum.slideXml, [
  bt23OpportunityName.replace("&", "&amp;").replace("'", "&apos;"),
  "99,9%",
  "Automatisch geprüft",
  "Human-reviewed exceptions",
]);

process.stdout.write("BT-17 COVER_01 renderer checks passed\n");
