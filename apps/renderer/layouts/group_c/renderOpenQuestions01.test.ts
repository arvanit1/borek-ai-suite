/** MS-19 renderer checks — two-column questions + assumptions. */

import assert from "node:assert/strict";

import type { OpenQuestions01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_c_open_questions_01.js";
import invoiceFixtureJson from "../../../../packages/contracts/fixtures/slide_spec/open_questions_01.minimal.json";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import {
  computeOpenQuestions01Layout,
  renderOpenQuestions01,
} from "./renderOpenQuestions01.js";
import {
  assertNoInlineDesignTokens,
  assertXmlContains,
  readRendererSource,
  renderToPptx,
} from "../rendererTestHelpers.js";

const invoiceFixture = invoiceFixtureJson as OpenQuestions01SlideSpec;
const rendererSource = readRendererSource(new URL("./renderOpenQuestions01.ts", import.meta.url));

assert.match(rendererSource, /MASTER_CONTENT_NAME/);
assert.match(rendererSource, /addBulletList\(/);
assert.match(rendererSource, /addSlideTitle\(/);
assertNoInlineDesignTokens(rendererSource);

const layout = computeOpenQuestions01Layout(true);
assert.deepEqual(computeOpenQuestions01Layout(true), layout);
assert.ok(layout.subtitle);
assert.equal(layout.left.heading.x, BorekSpacing.marginX);
assert.ok(
  Math.abs(
    layout.right.heading.x - (layout.left.heading.x + layout.left.heading.w) - BorekGrid.columnGap,
  ) < 1e-9,
);

function xmlText(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("'", "&apos;");
}

const original = structuredClone(invoiceFixture);
const first = await renderToPptx((pptx) => renderOpenQuestions01(pptx, invoiceFixture));
const second = await renderToPptx((pptx) => renderOpenQuestions01(pptx, invoiceFixture));
assert.deepEqual(invoiceFixture, original);
assert.equal(first.slideXml, second.slideXml);
assertXmlContains(first.slideXml, [
  invoiceFixture.title,
  invoiceFixture.left.heading,
  invoiceFixture.right.heading,
  ...invoiceFixture.left.items.map(xmlText),
  ...invoiceFixture.right.items.map(xmlText),
]);

const maximumFixture: OpenQuestions01SlideSpec = {
  schema_version: "1.0",
  layoutId: "OPEN_QUESTIONS_01",
  sectionLabel: "FRAGEN & ANNAHMEN".padEnd(32, "Ä"),
  title: "What still needs confirmation ".padEnd(72, "Ü"),
  subtitle: "Open questions & assumptions ".padEnd(100, "ß"),
  sourceChapterIds: ["11"],
  left: {
    heading: "Offene Fragen",
    items: Array.from({ length: 6 }, (_, index) =>
      `Frage ${index + 1}: ERP & Mailbox `.padEnd(120, String(index + 1)),
    ),
  },
  right: {
    heading: "Annahmen",
    items: Array.from({ length: 6 }, (_, index) =>
      `Annahme ${index + 1}: read-only `.padEnd(120, String(index + 1)),
    ),
  },
};
const maximum = await renderToPptx((pptx) => renderOpenQuestions01(pptx, maximumFixture));
assertXmlContains(maximum.slideXml, [
  "Offene Fragen",
  "Annahmen",
  maximumFixture.left.items[0]!.replace("&", "&amp;"),
  "Ä",
]);

const minimumFixture: OpenQuestions01SlideSpec = {
  schema_version: "1.0",
  layoutId: "OPEN_QUESTIONS_01",
  title: "Eine offene Frage",
  sourceChapterIds: ["11"],
  left: {
    heading: "Frage",
    items: ["Welches ERP-Feld gilt für PO & WE?"],
  },
  right: {
    heading: "Annahme",
    items: ["Mailbox bleibt read-only"],
  },
};
const minimum = await renderToPptx((pptx) => renderOpenQuestions01(pptx, minimumFixture));
assertXmlContains(minimum.slideXml, [
  "Eine offene Frage",
  "Frage",
  "Annahme",
  "Welches ERP-Feld gilt für PO &amp; WE?",
  "Mailbox bleibt read-only",
]);

process.stdout.write("MS-19 OPEN_QUESTIONS_01 renderer checks passed\n");
