/** MS-17 renderer checks — Invoice dark cards plus light MASTER_CONTENT variant. */

import assert from "node:assert/strict";

import type { Compliance01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_c_compliance_01.js";
import invoiceFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/compliance_01.minimal.json";
import {
  MASTER_CLOSING_NAME,
  registerMasterClosing,
} from "../../design_system/masters/MASTER_CLOSING.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { cardRowSizes, computeCardGridLayout } from "./cardGrid.js";
import { complianceItemTitle, renderCompliance01 } from "./renderCompliance01.js";
import {
  assertNoInlineDesignTokens,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "../rendererTestHelpers.js";

const invoiceFixture = invoiceFixtureJson as Compliance01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderCompliance01.ts", import.meta.url));

assert.match(rendererSource, /MASTER_CLOSING_NAME/);
assert.match(rendererSource, /MASTER_CONTENT_NAME/);
assert.match(rendererSource, /addContentCard\(/);
assert.match(rendererSource, /addSlideTitle\(/);
assertNoInlineDesignTokens(rendererSource);

assert.deepEqual(cardRowSizes(2), [2]);
assert.deepEqual(cardRowSizes(4), [2, 2]);
assert.deepEqual(cardRowSizes(6), [3, 3]);

const invoiceLayout = computeCardGridLayout(false, 2, true);
assert.deepEqual(computeCardGridLayout(false, 2, true), invoiceLayout);
assert.equal(invoiceLayout.cards.length, 2);
assert.equal(invoiceLayout.cards[0]?.x, BorekSpacing.marginX);

function xmlText(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("'", "&apos;");
}

const original = structuredClone(invoiceFixture);
const first = await renderToPptx((pptx) => renderCompliance01(pptx, invoiceFixture), {
  registerMaster: registerMasterClosing,
  expectedMasterName: MASTER_CLOSING_NAME,
});
const second = await renderToPptx((pptx) => renderCompliance01(pptx, invoiceFixture), {
  registerMaster: registerMasterClosing,
  expectedMasterName: MASTER_CLOSING_NAME,
});
assert.deepEqual(invoiceFixture, original, "renderer must not mutate its SlideSpec");
assert.equal(first.slideXml, second.slideXml, "same SlideSpec must produce deterministic slide XML");
assertXmlContains(first.slideXml, [
  invoiceFixture.sectionLabel ?? "",
  xmlText(invoiceFixture.title),
  ...invoiceFixture.items.flatMap((item) => [
    complianceItemTitle(item.icon),
    xmlText(item.text),
  ]),
]);

const lightFixture: Compliance01SlideSpec = {
  ...invoiceFixture,
  darkBackground: false,
  subtitle: "Light variant & Kontrolle",
};
const light = await renderToPptx((pptx) => renderCompliance01(pptx, lightFixture));
assertXmlContains(light.slideXml, [
  "Light variant &amp; Kontrolle",
  complianceItemTitle("lock"),
]);

process.stdout.write("MS-17 COMPLIANCE_01 renderer checks passed\n");
