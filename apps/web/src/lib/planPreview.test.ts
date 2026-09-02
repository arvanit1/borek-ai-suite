import assert from "node:assert/strict";

import { extractSlidePreviewRows, formatLayoutLabel, sortSlidesByOrder } from "./planPreview.js";
import type { PresentationPlanObject } from "./planTypes.js";

const samplePlan: PresentationPlanObject = {
  schema_version: "1.0",
  title: "Invoice Automation Proposal",
  slides: [
    {
      order: 3,
      purpose: "scope",
      layoutId: "SCOPE_01",
      frameworkReferences: ["chapter_3"],
    },
    {
      order: 1,
      purpose: "cover",
      layoutId: "COVER_01",
      frameworkReferences: ["opportunity"],
    },
    {
      order: 2,
      purpose: "context",
      layoutId: "CONTEXT_01",
      frameworkReferences: ["chapter_1", "chapter_2"],
    },
  ],
};

const sorted = sortSlidesByOrder(samplePlan.slides);
assert.deepEqual(
  sorted.map((slide) => slide.order),
  [1, 2, 3],
);

const rows = extractSlidePreviewRows(samplePlan);
assert.equal(rows.length, 3);
assert.deepEqual(rows[0], { order: 1, purpose: "cover", layoutId: "COVER_01" });
assert.deepEqual(rows[2], { order: 3, purpose: "scope", layoutId: "SCOPE_01" });

assert.equal(formatLayoutLabel("PROCESS_FLOW_01"), "Process flow");

console.log("planPreview tests passed");
