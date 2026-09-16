import assert from "node:assert/strict";

import {
  replaceNonConflictOpenItems,
  resolveOpenItemConflict,
  updateFrameworkArrayField,
  updateQualityRationale,
  updateQualityScore,
  updateRecordField,
} from "./frameworkFieldEdit.js";
import { EXPECTED_CHAPTER_COUNT, hasExpectedChapterCount } from "./frameworkEdit.js";
import type { FrameworkObject } from "./frameworkTypes.js";

const base: FrameworkObject = {
  schema_version: "1.0",
  opportunity_id: "00000000-0000-4000-8000-000000000001",
  title: "Invoice Automation",
  department: "Finance",
  status: "draft",
  priority_rank: null,
  quality_scores: {
    opportunity_rating: 70,
    conversation_quality: 65,
    build_readiness: 60,
    rationale: {
      opportunity_rating: "Clear pain",
      conversation_quality: "Some gaps",
      build_readiness: "Needs access confirmation",
    },
  },
  kpis: [{ name: "Automation rate", baseline: "0%", target: "80%", measured_via: "Ops report" }],
  systems: [],
  rules: [{ name: "Three-way match", logic: "Invoice, PO, and receipt must agree." }],
  exceptions: [],
  access_needs: [],
  evolution_stages: [],
  open_items: [],
  chapters: Array.from({ length: EXPECTED_CHAPTER_COUNT }, (_, index) => ({
    chapter_id: String(index),
    title: `Chapter ${index}`,
    body: "",
    source_refs: [],
  })),
  version: 1,
  generated_from: ["transcript-001"],
  previous_version_id: null,
  change_log: ["Initial generation"],
  created_at: "2026-08-24T12:00:00Z",
  updated_at: "2026-08-24T12:00:00Z",
};

assert.equal(hasExpectedChapterCount(base), true);

const scoreUpdated = updateQualityScore(base, "build_readiness", 75);
assert.equal(scoreUpdated.quality_scores.build_readiness, 75);

const rationaleUpdated = updateQualityRationale(base, "conversation_quality", "Updated rationale");
assert.equal(
  rationaleUpdated.quality_scores.rationale.conversation_quality,
  "Updated rationale",
);

const rulesUpdated = updateRecordField(base.rules, 0, "logic", "Updated rule logic");
assert.equal(rulesUpdated[0].logic, "Updated rule logic");

const withRules = updateFrameworkArrayField(base, "rules", rulesUpdated);
assert.equal((withRules.rules[0] as { logic: string }).logic, "Updated rule logic");

const conflictItems: Record<string, unknown>[] = [
  {
    description: "Conflicting monthly volume",
    item_type: "conflict",
    owner: "Process Manager",
    consequence_if_different: "Capacity changes.",
    conflict: {
      topic: "monthly volume",
      alternatives: [
        { value: "100", source_refs: [{ conversation_id: "C1", speaker_role: "operator", excerpt_pointer: "turn:1" }] },
        { value: "200", source_refs: [{ conversation_id: "C2", speaker_role: "manager", excerpt_pointer: "turn:2" }] },
      ],
      resolution: null,
    },
  },
  {
    description: "Confirm mailbox access",
    item_type: "dependency",
    owner: "IT",
    consequence_if_different: "Build waits.",
  },
];

const resolved = resolveOpenItemConflict(conflictItems, 0, "200");
assert.equal(
  ((resolved[0].conflict as { resolution: { selected_value: string } }).resolution.selected_value),
  "200",
);
assert.equal(resolved[1].item_type, "dependency");

const merged = replaceNonConflictOpenItems(conflictItems, [
  {
    description: "Updated mailbox access",
    item_type: "dependency",
    owner: "IT",
    consequence_if_different: "Build waits.",
  },
]);
assert.equal(merged[0].item_type, "conflict");
assert.equal(merged[1].description, "Updated mailbox access");

console.log("frameworkFieldEdit tests passed");
