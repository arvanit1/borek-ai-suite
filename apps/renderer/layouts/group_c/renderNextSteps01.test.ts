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

const minimumFixture: NextSteps01SlideSpec = {
  schema_version: "1.0",
  layoutId: "NEXT_STEPS_01",
  title: "Nächster Schritt",
  sourceChapterIds: ["13"],
  checklist: ["Mailbox-Pfad bestätigen"],
  steps: [{ number: 1, text: "Workshop für Ausnahme & Regeln" }],
  darkBackground: true,
};
const minimum = await renderToPptx((pptx) => renderNextSteps01(pptx, minimumFixture), {
  registerMaster: registerMasterClosing,
  expectedMasterName: MASTER_CLOSING_NAME,
});
assert.equal(computeNextSteps01Layout(false, true, 1).stepRows.length, 1);
assertXmlContains(minimum.slideXml, [
  "Nächster Schritt",
  "Mailbox-Pfad bestätigen",
  "Workshop für Ausnahme &amp; Regeln",
]);

const maximumFixture: NextSteps01SlideSpec = {
  schema_version: "1.0",
  layoutId: "NEXT_STEPS_01",
  sectionLabel: "NÄCHSTE SCHRITTE".padEnd(32, "Ä"),
  title: "What happens next für den Piloten ".padEnd(72, "Ü"),
  subtitle: "Checklist & numbered handover ".padEnd(100, "ß"),
  sourceChapterIds: ["13"],
  checklist: Array.from({ length: 6 }, (_, index) =>
    `Check ${index + 1}: ERP & Mailbox `.padEnd(72, String(index + 1)),
  ),
  steps: Array.from({ length: 6 }, (_, index) => ({
    number: index + 1,
    text: `Schritt ${index + 1}: Freigabe prüfen `.padEnd(100, String(index + 1)),
  })),
  darkBackground: true,
};
const maximum = await renderToPptx((pptx) => renderNextSteps01(pptx, maximumFixture), {
  registerMaster: registerMasterClosing,
  expectedMasterName: MASTER_CLOSING_NAME,
});
assert.equal(computeNextSteps01Layout(true, true, 6).stepRows.length, 6);
assertXmlContains(maximum.slideXml, [
  xmlText(maximumFixture.title),
  xmlText(maximumFixture.checklist[0]!),
  xmlText(maximumFixture.steps[5]!.text),
  "Ä",
]);

process.stdout.write("MS-20 NEXT_STEPS_01 renderer checks passed\n");
