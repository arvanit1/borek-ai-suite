import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { buildDeckBuffer } from "./deck_builder.js";
import { RenderServiceError, validateRenderRequest } from "./render_service.js";
import type { PresentationPlan, SlideSpecBase } from "./src/contracts.js";

function fixture(path: string): SlideSpecBase {
  return JSON.parse(
    readFileSync(new URL(`../../packages/contracts/fixtures/slide_spec/group_a/${path}`, import.meta.url), "utf8"),
  ) as SlideSpecBase;
}

const cover = fixture("cover_01.realistic.json");
const context = fixture("context_01.realistic.json");
const executiveSummary = JSON.parse(
  readFileSync(
    new URL(
      "../../packages/contracts/fixtures/slide_spec/summary/executive_summary_01.realistic.json",
      import.meta.url,
    ),
    "utf8",
  ),
) as SlideSpecBase;
const plan = {
  schema_version: "1.0",
  title: "Renderer contract test",
  slides: [
    { order: 1, purpose: "cover", layoutId: "COVER_01", frameworkReferences: ["opportunity"] },
    {
      order: 2,
      purpose: "context",
      layoutId: "CONTEXT_01",
      frameworkReferences: ["chapter_1", "chapter_2"],
    },
  ],
} as PresentationPlan;

const valid = validateRenderRequest({ presentationPlan: plan, slideSpecs: [cover, context] });
assert.equal(valid.slideSpecs.length, 2);

assert.throws(
  () => validateRenderRequest({ presentationPlan: plan, slideSpecs: [cover] }),
  (error: unknown) => error instanceof RenderServiceError && error.code === "SLIDE_COUNT_MISMATCH",
);

await assert.rejects(
  () =>
    buildDeckBuffer([
      {
        schema_version: "1.0",
        slideId: "slide_02",
        layoutId: "UNKNOWN_LAYOUT_99" as SlideSpecBase["layoutId"],
        title: "Summary",
        sourceChapterIds: ["1"],
      } as SlideSpecBase,
    ]),
  /No render function registered|has no implemented renderer/,
);

const summaryDeck = await buildDeckBuffer([executiveSummary]);
assert.ok(summaryDeck.length > 10_000);
assert.equal(summaryDeck.subarray(0, 2).toString(), "PK");

const deck = await buildDeckBuffer([cover, context]);
assert.ok(deck.length > 10_000);
assert.equal(deck.subarray(0, 2).toString(), "PK");
