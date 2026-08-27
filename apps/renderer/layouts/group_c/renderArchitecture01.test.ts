/** MS-16 renderer checks — Invoice fixture, 2–8 nodes, German + special characters. */

import assert from "node:assert/strict";

import type { Architecture01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_c_architecture_01.js";
import invoiceFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/architecture_01.minimal.json";
import { architectureNodeBadgeSize } from "../../design_system/components/addArchitectureNode.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import {
  architectureRowSizes,
  computeArchitecture01Layout,
  renderArchitecture01,
} from "./renderArchitecture01.js";
import {
  assertNoInlineDesignTokens,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "../rendererTestHelpers.js";

const invoiceFixture = invoiceFixtureJson as Architecture01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderArchitecture01.ts", import.meta.url));

assert.match(rendererSource, /MASTER_CONTENT_NAME/);
assert.match(rendererSource, /addSlideTitle\(/);
assert.match(rendererSource, /addSectionLabel\(/);
assert.match(rendererSource, /addArchitectureNode\(/);
assert.match(rendererSource, /addConnector\(/);
assertNoInlineDesignTokens(rendererSource);

assert.deepEqual(architectureRowSizes(2), [2]);
assert.deepEqual(architectureRowSizes(3), [3]);
assert.deepEqual(architectureRowSizes(4), [2, 2]);
assert.deepEqual(architectureRowSizes(5), [3, 2]);
assert.deepEqual(architectureRowSizes(8), [4, 4]);

const noSubtitleLayout = computeArchitecture01Layout(false, 2);
const invoiceLayout = computeArchitecture01Layout(true, 4);
assert.deepEqual(computeArchitecture01Layout(true, 4), invoiceLayout, "layout must be deterministic");
assert.equal(noSubtitleLayout.subtitle, undefined);
assert.ok(invoiceLayout.subtitle);
assert.equal(invoiceLayout.rows.length, 2);
assert.equal(invoiceLayout.nodes.length, 4);
assert.equal(invoiceLayout.rows[0]?.length, 2);
assert.equal(invoiceLayout.rows[1]?.length, 2);
assert.equal(invoiceLayout.nodes[0]?.x, BorekSpacing.marginX + architectureNodeBadgeSize() / 2);
assert.ok(
  Math.abs(
    invoiceLayout.rows[0]![1]!.x -
      (invoiceLayout.rows[0]![0]!.x + invoiceLayout.rows[0]![0]!.w) -
      BorekGrid.columnGap,
  ) < 1e-9,
);

const original = structuredClone(invoiceFixture);
const first = await renderToPptx((pptx) => renderArchitecture01(pptx, invoiceFixture));
const second = await renderToPptx((pptx) => renderArchitecture01(pptx, invoiceFixture));
assert.deepEqual(invoiceFixture, original, "renderer must not mutate its SlideSpec");
assert.equal(first.slideXml, second.slideXml, "same SlideSpec must produce deterministic slide XML");
function xmlText(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("'", "&apos;");
}

assertXmlContains(first.slideXml, [
  ...(invoiceFixture.sectionLabel ? [invoiceFixture.sectionLabel] : []),
  invoiceFixture.title,
  ...(invoiceFixture.subtitle ? [xmlText(invoiceFixture.subtitle)] : []),
  ...invoiceFixture.components.flatMap((component) => [
    xmlText(component.title),
    xmlText(component.description),
    String(component.number),
  ]),
]);
assert.match(first.slideXml, /ellipse|prst="ellipse"/);
assert.match(first.slideXml, /roundRect|prst="roundRect"/);

const twoNodeLayout = computeArchitecture01Layout(false, 2);
assert.equal(twoNodeLayout.rows.length, 1);
const twoNode = await renderToPptx((pptx) =>
  renderArchitecture01(pptx, {
    schema_version: "1.0",
    layoutId: "ARCHITECTURE_01",
    title: "Zwei Systeme",
    sourceChapterIds: ["6", "7"],
    components: [
      { number: 1, title: "Mailbox", description: "Quelle" },
      { number: 2, title: "ERP", description: "Buchungen" },
    ],
  }),
);
assertXmlContains(twoNode.slideXml, ["Zwei Systeme", "Mailbox", "ERP"]);

const maximumFixture: Architecture01SlideSpec = {
  schema_version: "1.0",
  layoutId: "ARCHITECTURE_01",
  sectionLabel: "ARCHITEKTUR & FLOW".padEnd(32, "Ä"),
  title: "How It Is Built für geprüfte Systeme ".padEnd(72, "Ü"),
  subtitle: "Systems, data flow & integration ".padEnd(100, "ß"),
  sourceChapterIds: ["6", "7"],
  components: Array.from({ length: 8 }, (_, index) => ({
    number: index + 1,
    title: `Node ${index + 1} Prüfung `.padEnd(40, String(index + 1)),
    description: `Deutsch & English node ${index + 1} `.padEnd(100, "X"),
  })),
};
const maximum = await renderToPptx((pptx) => renderArchitecture01(pptx, maximumFixture));
assert.equal(computeArchitecture01Layout(true, 8).nodes.length, 8);
assertXmlContains(maximum.slideXml, [
  maximumFixture.title,
  maximumFixture.components[0]!.title,
  maximumFixture.components[7]!.title,
  maximumFixture.components[7]!.description.replace("&", "&amp;"),
  "&amp;",
  "Ä",
]);

process.stdout.write("MS-16 ARCHITECTURE_01 renderer checks passed\n");
