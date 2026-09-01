import assert from "node:assert/strict";

import { replaceArrayItem, replaceRecordField, updateChapterBodyValue } from "./frameworkNestedEdit.js";
import type { FrameworkChapter } from "./frameworkTypes.js";

const chapter: FrameworkChapter = {
  chapter_id: "3",
  title: "Aim",
  body: [
    {
      block: "table",
      columns: ["KPI", "Target"],
      rows: [
        ["auto-match", "85%"],
        ["cycle time", "open"],
      ],
      items: ["Keep exceptions human-controlled"],
      meta: { owner: "Finance" },
      source_refs: [{ conversation_id: "C1", speaker_role: "Sandra", excerpt_pointer: "turn:5" }],
    },
  ],
  source_refs: [],
};

const rows = (chapter.body as Record<string, unknown>[])[0].rows as string[][];
const editedRows = replaceArrayItem(rows, 0, replaceArrayItem(rows[0], 1, "90%"));
assert.equal(editedRows[0][1], "90%");
assert.equal(rows[0][1], "85%");

const record = replaceRecordField({ owner: "Finance" }, "owner", "Operations");
assert.equal(record.owner, "Operations");

const withCell = updateChapterBodyValue(chapter, 0, "rows", editedRows);
assert.equal(((withCell.body as Record<string, unknown>[])[0].rows as string[][])[0][1], "90%");
assert.deepEqual((withCell.body as Record<string, unknown>[])[0].source_refs, [
  { conversation_id: "C1", speaker_role: "Sandra", excerpt_pointer: "turn:5" },
]);

const withBullet = updateChapterBodyValue(chapter, 0, "items", ["Updated bullet"]);
assert.deepEqual((withBullet.body as Record<string, unknown>[])[0].items, ["Updated bullet"]);

console.log("frameworkNestedEdit tests passed");
