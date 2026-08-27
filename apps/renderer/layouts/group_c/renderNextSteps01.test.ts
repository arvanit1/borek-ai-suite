/** MS-20 renderer checks — dark checklist + numbered steps. */

import assert from "node:assert/strict";

import type { NextSteps01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_c_next_steps_01.js";
import invoiceFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/next_steps_01.minimal.json";
import {
  MASTER_CLOSING_NAME,
  registerMasterClosing,
} from "../../design_system/masters/MASTER_CLOSING.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import {
  computeNextSteps01Layout,
  renderNextSteps01,
} from "./renderNextSteps01.js";
import {
  assertNoInlineDesignTokens,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "../rendererTestHelpers.js";

const invoiceFixture = invoiceFixtureJson as NextSteps01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderNextSteps01.ts", import.meta.url));

assert.match(rendererSource, /MASTER_CLOSING_NAME/);
assert.match(rendererSource, /addBulletList\(/);
assert.match(rendererSource, /addNumberBadge\(/);
assert.match(rendererSource, /addSlideTitle\(/);
assertNoInlineDesignTokens(rendererSource);

const layout = computeNextSteps01Layout(false, true, 2);
assert.deepEqual(computeNextSteps01Layout(false, true, 2), layout);
assert.equal(layout.checklist.x, BorekSpacing.marginX);
assert.equal(layout.stepRows.length, 2);
assert.ok(layout.steps.x > layout.checklist.x);

function xmlText(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("'", "&apos;");
}

const original = structuredClone(invoiceFixture);
const first = await renderToPptx((pptx) => renderNextSteps01(pptx, invoiceFixture), {
  registerMaster: registerMasterClosing,
  expectedMasterName: MASTER_CLOSING_NAME,
});
const second = await renderToPptx((pptx) => renderNextSteps01(pptx, invoiceFixture), {
  registerMaster: registerMasterClosing,
  expectedMasterName: MASTER_CLOSING_NAME,
});
assert.deepEqual(invoiceFixture, original);
assert.equal(first.slideXml, second.slideXml);
assertXmlContains(first.slideXml, [
  invoiceFixture.title,
  ...invoiceFixture.checklist.map(xmlText),
  ...invoiceFixture.steps.flatMap((step) => [String(step.number), xmlText(step.text)]),
]);
assert.match(first.slideXml, /ellipse|prst="ellipse"/);

const lightFixture: NextSteps01SlideSpec = {
  ...invoiceFixture,
  darkBackground: false,
  subtitle: "Light closing & nächste Schritte",
};
const light = await renderToPptx((pptx) => renderNextSteps01(pptx, lightFixture));
assertXmlContains(light.slideXml, ["Light closing &amp; nächste Schritte", "1"]);

process.stdout.write("MS-20 NEXT_STEPS_01 renderer checks passed\n");
