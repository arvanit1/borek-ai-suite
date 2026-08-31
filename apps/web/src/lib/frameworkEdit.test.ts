import assert from "node:assert/strict";

import {
  EXPECTED_CHAPTER_COUNT,
  countChaptersWithSourceRefs,
  formatSourceRefLabel,
  hasExpectedChapterCount,
  canEditFramework,
  isFrameworkConfirmed,
  isFrameworkEditable,
  updateChapter,
  updateChapterBodyField,
  updateChapterStringBody,
  updateFrameworkRootField,
} from "./frameworkEdit.js";
import type { FrameworkObject } from "./frameworkTypes.js";

const sampleFramework: FrameworkObject = {
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
  kpis: [],
  systems: [],
  rules: [],
  exceptions: [],
  access_needs: [],
  evolution_stages: [],
  open_items: [],
  chapters: Array.from({ length: EXPECTED_CHAPTER_COUNT }, (_, index) => ({
    chapter_id: String(index),
    title: `Chapter ${index}`,
    body: index === 1 ? [{ summary: "Original summary" }] : "",
    source_refs:
      index === 1
        ? [
            {
              conversation_id: "C1",
              speaker_role: "dept_head",
              excerpt_pointer: "turn-12",
            },
          ]
        : [],
  })),
  version: 1,
  generated_from: ["transcript-001"],
  previous_version_id: null,
  change_log: ["Initial generation"],
  created_at: "2026-08-24T12:00:00Z",
  updated_at: "2026-08-24T12:00:00Z",
};

assert.equal(isFrameworkEditable("draft"), true);
assert.equal(isFrameworkEditable("in_review"), true);
assert.equal(isFrameworkEditable("confirmed"), false);
assert.equal(isFrameworkConfirmed("confirmed"), true);
assert.equal(canEditFramework("draft"), true);
assert.equal(canEditFramework("in_review"), true);
assert.equal(canEditFramework("draft", "in_review"), true);
assert.equal(canEditFramework("confirmed"), false);
assert.equal(canEditFramework("draft", "confirmed"), false);
assert.equal(hasExpectedChapterCount(sampleFramework), true);
assert.equal(countChaptersWithSourceRefs(sampleFramework), 1);

const refLabel = formatSourceRefLabel(sampleFramework.chapters[1].source_refs[0]);
assert.match(refLabel, /C1/);
assert.match(refLabel, /dept_head/);

const renamed = updateFrameworkRootField(sampleFramework, "title", "Updated title");
assert.equal(renamed.title, "Updated title");

const chapter = updateChapterStringBody(sampleFramework.chapters[0], "Edited intro");
assert.equal(chapter.body, "Edited intro");

const blockEdit = updateChapterBodyField(sampleFramework.chapters[1], 0, "summary", "New summary");
assert.equal((blockEdit.body as Record<string, unknown>[])[0].summary, "New summary");

const withChapter = updateChapter(sampleFramework, 1, blockEdit);
assert.equal((withChapter.chapters[1].body as Record<string, unknown>[])[0].summary, "New summary");

console.log("frameworkEdit tests passed");
