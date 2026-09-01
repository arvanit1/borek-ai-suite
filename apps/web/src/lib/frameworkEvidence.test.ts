import assert from "node:assert/strict";

import {
  countFactSourceRefs,
  isBlockTypeKey,
  isConversationRef,
  isEditableContentKey,
  provenanceKindFromValue,
  sourceRefsForBlock,
  sourceRefsForFactDisplay,
} from "./frameworkEvidence.js";
import type { FrameworkChapter } from "./frameworkTypes.js";

const chapterRef = {
  conversation_id: "C-CHAPTER",
  speaker_role: "dept_head",
  excerpt_pointer: "turn-1",
};
const factA = {
  conversation_id: "C-A",
  speaker_role: "operator",
  excerpt_pointer: "turn-12",
};
const factB = {
  conversation_id: "C-B",
  speaker_role: "it",
  excerpt_pointer: "turn-34",
};

const chapter: FrameworkChapter = {
  chapter_id: "2",
  title: "Starting point",
  body: [
    { block: "prose", text: "Manual matching today.", source_refs: [factA] },
    { block: "table", columns: ["KPI"], rows: [["auto-match"]], source_refs: [factB] },
    { block: "prose", text: "Scaffolding with no citation." },
  ],
  source_refs: [chapterRef],
};

assert.equal(isConversationRef(factA), true);
assert.equal(isConversationRef({ conversation_id: "C1" }), false);
assert.equal(isEditableContentKey("text"), true);
assert.equal(isEditableContentKey("source_refs"), false);
assert.equal(isBlockTypeKey("block"), true);

assert.deepEqual(sourceRefsForBlock(chapter.body[0] as Record<string, unknown>), [factA]);
assert.deepEqual(sourceRefsForBlock(chapter.body[2] as Record<string, unknown>), []);
assert.deepEqual(
  sourceRefsForFactDisplay(chapter, chapter.body[0] as Record<string, unknown>),
  [factA],
);
assert.notDeepEqual(
  sourceRefsForFactDisplay(chapter, chapter.body[0] as Record<string, unknown>),
  chapter.source_refs,
);
assert.deepEqual(sourceRefsForFactDisplay(chapter), []);
assert.equal(countFactSourceRefs(chapter), 2);
assert.equal(
  provenanceKindFromValue({ provenance: "ai_inference", text: "Guess" }),
  "AI inference",
);
assert.equal(provenanceKindFromValue({ origin: "user_input" }), "User input");
assert.equal(provenanceKindFromValue({ text: "plain" }), null);

const stringChapter: FrameworkChapter = {
  chapter_id: "0",
  title: "About this document",
  body: "Narrative chapter",
  source_refs: [chapterRef],
};
assert.equal(countFactSourceRefs(stringChapter), 1);
assert.deepEqual(sourceRefsForFactDisplay(stringChapter), [chapterRef]);

console.log("frameworkEvidence tests passed");
