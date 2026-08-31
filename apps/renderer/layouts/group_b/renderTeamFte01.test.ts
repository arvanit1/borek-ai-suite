/** JJ-18 focused renderer tests. */

import assert from "node:assert/strict";

import type { TeamFte01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_b_team_fte_01.js";
import minimalFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_b/team_fte_01.minimal.json";
import realisticFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/group_b/team_fte_01.realistic.json";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import {
  computeTeamFte01Layout,
  renderTeamFte01,
  teamFteRowSizes,
} from "./renderTeamFte01.js";
import {
  assertNoInlineDesignTokens,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "../rendererTestHelpers.js";
import { JJ20_ENGLISH, JJ20_GERMAN, JJ20_SPECIAL, padTo, xmlForAssert } from "./jj20Coverage.js";

const minimalFixture = minimalFixtureJson as TeamFte01SlideSpec;
const realisticFixture = realisticFixtureJson as TeamFte01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderTeamFte01.ts", import.meta.url));

assert.match(rendererSource, /MASTER_CONTENT_NAME/);
assert.match(rendererSource, /addSlideTitle\(/);
assert.match(rendererSource, /addSectionLabel\(/);
assert.match(rendererSource, /addContentCard\(/);
assert.match(rendererSource, /addKpiCard\(/);
assertNoInlineDesignTokens(rendererSource);

assert.deepEqual(teamFteRowSizes(1), [1]);
assert.deepEqual(teamFteRowSizes(3), [3]);
assert.deepEqual(teamFteRowSizes(4), [2, 2]);
assert.deepEqual(teamFteRowSizes(6), [3, 3]);

const noSubtitleLayout = computeTeamFte01Layout(false, 1, 1);
const fourLayout = computeTeamFte01Layout(true, 4, 3);
assert.deepEqual(computeTeamFte01Layout(true, 4, 3), fourLayout, "layout must be deterministic");
assert.equal(noSubtitleLayout.subtitle, undefined);
assert.ok(fourLayout.subtitle);
assert.equal(fourLayout.roles.length, 4);
assert.equal(fourLayout.summary.length, 3);
assert.equal(fourLayout.roles[0]?.x, BorekSpacing.marginX);
assert.ok(fourLayout.summary[0]!.y > fourLayout.roles[0]!.y + fourLayout.roles[0]!.h);
assert.ok(
  Math.abs(
    fourLayout.summary[1]!.x -
      (fourLayout.summary[0]!.x + fourLayout.summary[0]!.w) -
      BorekGrid.columnGap,
  ) < 1e-9,
);

for (const fixture of [minimalFixture, realisticFixture]) {
  const original = structuredClone(fixture);
  const first = await renderToPptx((pptx) => renderTeamFte01(pptx, fixture));
  const second = await renderToPptx((pptx) => renderTeamFte01(pptx, fixture));
  assert.deepEqual(fixture, original, "renderer must not mutate its SlideSpec");
  assert.equal(first.slideXml, second.slideXml, "same SlideSpec must produce deterministic slide XML");
  assertXmlContains(first.slideXml, [
    ...(fixture.sectionLabel ? [fixture.sectionLabel] : []),
    fixture.title,
    ...(fixture.subtitle ? [fixture.subtitle] : []),
    ...fixture.roles.flatMap((role) => [role.role, role.fte, role.responsibility]),
    ...fixture.summary.flatMap((stat) => [stat.label, stat.value]),
  ]);
}

const maximumFixture: TeamFte01SlideSpec = {
  schema_version: "1.0",
  layoutId: "TEAM_FTE_01",
  sectionLabel: "TEAM & KAPAZITÄT".padEnd(32, "Ä"),
  title: "Who is needed and for how long ".padEnd(72, "Ü"),
  subtitle: "Client and delivery roles & first-release capacity ".padEnd(100, "ß"),
  sourceChapterIds: ["10"],
  roles: Array.from({ length: 6 }, (_, index) => ({
    role: `Rolle ${index + 1} Prüfung `.padEnd(32, "R"),
    fte: index % 2 === 0 ? "0.5" : "1–2",
    responsibility: `Deutsch & English duty ${index + 1} `.padEnd(80, "D"),
  })),
  summary: [
    { label: "Total FTE".padEnd(24, "T"), value: "4.5" },
    { label: "Milestones".padEnd(24, "M"), value: "8" },
    { label: "Duration".padEnd(24, "W"), value: "14 weeks" },
    { label: "Standorte".padEnd(24, "S"), value: "2 sites" },
  ],
};
const maximum = await renderToPptx((pptx) => renderTeamFte01(pptx, maximumFixture));
assert.equal(computeTeamFte01Layout(true, 6, 4).roles.length, 6);
assert.equal(computeTeamFte01Layout(true, 6, 4).summary.length, 4);
assertXmlContains(maximum.slideXml, [
  maximumFixture.title,
  maximumFixture.roles[5]!.role,
  maximumFixture.roles[5]!.responsibility.replace("&", "&amp;"),
  "1–2",
  "4.5",
  "&amp;",
  "Ä",
]);

const englishFixture: TeamFte01SlideSpec = {
  schema_version: "1.0",
  layoutId: "TEAM_FTE_01",
  title: JJ20_ENGLISH,
  sourceChapterIds: ["10"],
  roles: [{ role: "Process owner", fte: "0.3", responsibility: "Approve matching rules" }],
  summary: [{ label: "Total FTE", value: "0.3" }],
};
const germanFixture: TeamFte01SlideSpec = {
  schema_version: "1.0",
  layoutId: "TEAM_FTE_01",
  title: JJ20_GERMAN,
  sourceChapterIds: ["10"],
  roles: [{ role: "Prozesseigner", fte: "0,3", responsibility: "Freigabe der Prüfregeln" }],
  summary: [{ label: "Gesamt-FTE", value: "0,3" }],
};
const specialLongFixture: TeamFte01SlideSpec = {
  schema_version: "1.0",
  layoutId: "TEAM_FTE_01",
  title: padTo(`${JJ20_SPECIAL} team `, 72),
  sourceChapterIds: ["10"],
  roles: [
    {
      role: padTo("Long role name ", 32),
      fte: "1–2",
      responsibility: padTo("Deutsch & English duty ", 80),
    },
  ],
  summary: [{ label: padTo("Capacity", 24), value: "1–2 FTE" }],
};

const english = await renderToPptx((pptx) => renderTeamFte01(pptx, englishFixture));
const german = await renderToPptx((pptx) => renderTeamFte01(pptx, germanFixture));
const specialLong = await renderToPptx((pptx) => renderTeamFte01(pptx, specialLongFixture));
assertXmlContains(english.slideXml, [JJ20_ENGLISH, "Process owner", "0.3"]);
assertXmlContains(german.slideXml, [JJ20_GERMAN, "Prozesseigner", "Gesamt-FTE"]);
assert.equal(specialLongFixture.title.length, 72);
assert.equal(specialLongFixture.roles[0]!.role.length, 32);
assertXmlContains(specialLong.slideXml, [xmlForAssert(JJ20_SPECIAL), "&amp;", "Ä", "1–2"]);

process.stdout.write("JJ-18 TEAM_FTE_01 renderer checks passed\n");
