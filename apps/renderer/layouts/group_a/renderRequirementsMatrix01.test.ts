/** BT-21 renderer checks and BT-23 Group A coverage. */

import assert from "node:assert/strict";

import type { RequirementsMatrix01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_a_requirements_matrix_01.js";
import minimalFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_a/requirements_matrix_01.minimal.json";
import realisticFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_a/requirements_matrix_01.realistic.json";
import {
  formatRequirementStatusLabel,
  resolveRequirementStatusColors,
  type RequirementStatus,
} from "../../design_system/tokens/requirement_status.js";
import {
  computeRequirementsMatrix01Layout,
  renderRequirementsMatrix01,
} from "./renderRequirementsMatrix01.js";
import {
  HARDCODED_HEX_PATTERN,
  INLINE_FONT_FAMILY_PATTERN,
  INLINE_FONT_SIZE_PATTERN,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "./rendererTestHelpers.js";

const minimalFixture = minimalFixtureJson as RequirementsMatrix01SlideSpec;
const realisticFixture = realisticFixtureJson as RequirementsMatrix01SlideSpec;
const rendererSource = readRendererSource(
  new URL("./renderRequirementsMatrix01.ts", import.meta.url),
);
const bt23OpportunityName = "Long opportunity ä ö ü Ä Ö Ü ß & / % + (Pilot's) -";
const statuses: readonly RequirementStatus[] = ["included", "partial", "later"];

assert.match(rendererSource, /MASTER_CONTENT_NAME/);
assert.match(rendererSource, /addSlideTitle\(/);
assert.match(rendererSource, /addSectionLabel\(/);
assert.match(rendererSource, /addDataTable\(/);
assert.match(rendererSource, /resolveRequirementStatusColors\(/);
assert.match(rendererSource, /formatRequirementStatusLabel\(/);
assert.match(rendererSource, /parseRequirementStatus\(/);
assert.match(rendererSource, /type RequirementStatus/);
assert.deepEqual([...rendererSource.matchAll(HARDCODED_HEX_PATTERN)], []);
assert.deepEqual([...rendererSource.matchAll(INLINE_FONT_SIZE_PATTERN)], []);
assert.deepEqual([...rendererSource.matchAll(INLINE_FONT_FAMILY_PATTERN)], []);
assert.doesNotMatch(rendererSource, /\b(?:fetch|axios|OpenAI)\b/);

const noSubtitleLayout = computeRequirementsMatrix01Layout(false, 1);
const maximumLayout = computeRequirementsMatrix01Layout(true, 6);
assert.deepEqual(
  computeRequirementsMatrix01Layout(true, 6),
  maximumLayout,
  "layout must be deterministic",
);
assert.equal(noSubtitleLayout.subtitle, undefined);
assert.ok(maximumLayout.subtitle);
assert.equal(noSubtitleLayout.tables.length, 1);
assert.equal(maximumLayout.tables.length, 2);
assert.equal(maximumLayout.statusPills.length, 6);
for (const pill of maximumLayout.statusPills) {
  assert.ok(maximumLayout.tables.some((table) =>
    pill.x >= table.x &&
    pill.y >= table.y &&
    pill.x + pill.w <= table.x + table.w &&
    pill.y + pill.h <= table.y + table.h,
  ));
}

for (const fixture of [minimalFixture, realisticFixture]) {
  const original = structuredClone(fixture);
  const first = await renderToPptx((pptx) => renderRequirementsMatrix01(pptx, fixture));
  const second = await renderToPptx((pptx) => renderRequirementsMatrix01(pptx, fixture));
  assert.deepEqual(fixture, original, "renderer must not mutate its SlideSpec");
  assert.equal(first.slideXml, second.slideXml, "same SlideSpec must produce deterministic slide XML");
  assertXmlContains(first.slideXml, [
    ...(fixture.sectionLabel ? [fixture.sectionLabel] : []),
    fixture.title,
    ...(fixture.subtitle ? [fixture.subtitle] : []),
    "Requirement",
    "Status",
    ...fixture.requirements.flatMap((requirement) => [
      requirement.category,
      requirement.title,
      formatRequirementStatusLabel(requirement.status),
    ]),
  ]);
  for (const requirement of fixture.requirements) {
    const colors = resolveRequirementStatusColors(requirement.status);
    assert.match(first.slideXml, new RegExp(colors.fill));
    assert.match(first.slideXml, new RegExp(colors.text));
    assert.match(first.slideXml, new RegExp(colors.border));
  }
}

for (let requirementCount = 1; requirementCount <= 6; requirementCount += 1) {
  const cardinalityFixture: RequirementsMatrix01SlideSpec = {
    schema_version: "1.0",
    layoutId: "REQUIREMENTS_MATRIX_01",
    title: `Requirements ${requirementCount}`,
    sourceChapterIds: ["5"],
    requirements: Array.from({ length: requirementCount }, (_, index) => ({
      category: String.fromCharCode(65 + index),
      title: `Requirement ${index + 1}`,
      status: statuses[index % statuses.length],
    })),
  };
  const cardinalityLayout = computeRequirementsMatrix01Layout(false, requirementCount);
  const rendered = await renderToPptx((pptx) =>
    renderRequirementsMatrix01(pptx, cardinalityFixture),
  );

  assert.equal(cardinalityLayout.statusPills.length, requirementCount);
  assert.equal(cardinalityLayout.tables.length, requirementCount > 3 ? 2 : 1);
  assertXmlContains(
    rendered.slideXml,
    cardinalityFixture.requirements.flatMap((requirement) => [
      requirement.category,
      requirement.title,
      formatRequirementStatusLabel(requirement.status),
    ]),
  );
}

const maximumFixture: RequirementsMatrix01SlideSpec = {
  schema_version: "1.0",
  layoutId: "REQUIREMENTS_MATRIX_01",
  sectionLabel: "ANFORDERUNGEN & STATUS".padEnd(32, "Ä"),
  title: bt23OpportunityName.padEnd(72, "X"),
  subtitle: "German & English requirements with approved status semantics ".padEnd(100, "ß"),
  sourceChapterIds: ["5"],
  requirements: Array.from({ length: 6 }, (_, index) => ({
    category: `KAT-${index + 1}`.padEnd(12, "X"),
    title: `Anforderung ${index + 1} & requirement `.padEnd(48, String(index + 1)),
    status: statuses[index % statuses.length],
  })),
};
assert.equal(
  maximumFixture.title.length,
  72,
  "BT-23 requirements opportunity name must reach BT-15 max",
);
const maximum = await renderToPptx((pptx) =>
  renderRequirementsMatrix01(pptx, maximumFixture),
);
assertXmlContains(maximum.slideXml, [
  bt23OpportunityName.replace("&", "&amp;").replace("'", "&apos;"),
  maximumFixture.subtitle!.replace("&", "&amp;"),
  maximumFixture.requirements[5].title.replace("&", "&amp;"),
  "Included",
  "Partial",
  "Later",
]);

process.stdout.write("BT-21 REQUIREMENTS_MATRIX_01 renderer checks passed\n");
