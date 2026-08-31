/** MS-18 renderer checks — non-monetary criteria cards, German + special characters. */

import assert from "node:assert/strict";

import type { SuccessMetrics01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_c_success_metrics_01.js";
import invoiceFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/success_metrics_01.minimal.json";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { cardRowSizes, computeCardGridLayout } from "./cardGrid.js";
import { renderSuccessMetrics01 } from "./renderSuccessMetrics01.js";
import {
  assertNoInlineDesignTokens,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "../rendererTestHelpers.js";

const invoiceFixture = invoiceFixtureJson as SuccessMetrics01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderSuccessMetrics01.ts", import.meta.url));

assert.match(rendererSource, /MASTER_CONTENT_NAME/);
assert.match(rendererSource, /addKpiCard\(/);
assert.match(rendererSource, /addSlideTitle\(/);
assert.doesNotMatch(rendererSource, /€|\$|EUR|USD/);
assertNoInlineDesignTokens(rendererSource);

assert.deepEqual(cardRowSizes(2), [2]);
const layout = computeCardGridLayout(false, 2);
assert.equal(layout.cards[0]?.x, BorekSpacing.marginX);

function xmlText(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("'", "&apos;");
}

const original = structuredClone(invoiceFixture);
const first = await renderToPptx((pptx) => renderSuccessMetrics01(pptx, invoiceFixture));
const second = await renderToPptx((pptx) => renderSuccessMetrics01(pptx, invoiceFixture));
assert.deepEqual(invoiceFixture, original, "renderer must not mutate its SlideSpec");
assert.equal(first.slideXml, second.slideXml);
assert.doesNotMatch(first.slideXml, /€|\$|EUR|USD/);
assertXmlContains(first.slideXml, [
  invoiceFixture.title,
  ...invoiceFixture.criteria.flatMap((criterion) => [
    xmlText(criterion.title),
    xmlText(criterion.description),
  ]),
]);

const maximumFixture: SuccessMetrics01SlideSpec = {
  schema_version: "1.0",
  layoutId: "SUCCESS_METRICS_01",
  sectionLabel: "ERFOLG & METRIKEN".padEnd(32, "Ä"),
  title: "How we measure success ohne Preise ".padEnd(72, "Ü"),
  subtitle: "Non-monetary criteria only ".padEnd(100, "ß"),
  sourceChapterIds: ["3", "9"],
  criteria: Array.from({ length: 6 }, (_, index) => ({
    title: `Kriterium ${index + 1} `.padEnd(48, String(index + 1)),
    description: `Deutsch & English check ${index + 1} `.padEnd(160, "X"),
  })),
};
const maximum = await renderToPptx((pptx) => renderSuccessMetrics01(pptx, maximumFixture));
assertXmlContains(maximum.slideXml, [
  maximumFixture.criteria[0]!.title,
  maximumFixture.criteria[5]!.description.replace("&", "&amp;"),
  "Ä",
]);
assert.doesNotMatch(maximum.slideXml, /€|\$|EUR|USD/);

const minimumFixture: SuccessMetrics01SlideSpec = {
  schema_version: "1.0",
  layoutId: "SUCCESS_METRICS_01",
  title: "Ein Kriterium",
  sourceChapterIds: ["3", "9"],
  criteria: [{ title: "Trefferquote", description: "Ohne manuellen Eingriff & Wartezeit" }],
};
const minimum = await renderToPptx((pptx) => renderSuccessMetrics01(pptx, minimumFixture));
assert.equal(computeCardGridLayout(false, 1).cards.length, 1);
assertXmlContains(minimum.slideXml, [
  "Ein Kriterium",
  "Trefferquote",
  "Ohne manuellen Eingriff &amp; Wartezeit",
]);
assert.doesNotMatch(minimum.slideXml, /€|\$|EUR|USD/);

process.stdout.write("MS-18 SUCCESS_METRICS_01 renderer checks passed\n");
