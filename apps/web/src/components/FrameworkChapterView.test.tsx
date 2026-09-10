import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { FrameworkChapterView } from "./FrameworkChapterView.js";
import type { FrameworkChapter } from "@/lib/frameworkTypes";

const chapter: FrameworkChapter = {
  chapter_id: "7",
  title: "What the client needs to provide",
  body: "ERP access is still an open item.",
  source_refs: [],
};

const idle = renderToStaticMarkup(
  <FrameworkChapterView
    chapter={chapter}
    editable
    onChange={() => undefined}
    onRegenerate={() => undefined}
  />,
);
assert.match(idle, /Regenerate chapter/);
assert.match(idle, /Regenerate rewrites this chapter from the transcripts/);
assert.doesNotMatch(idle, /data-regenerating="true"/);
assert.doesNotMatch(idle, /Updating this chapter/);

const running = renderToStaticMarkup(
  <FrameworkChapterView
    chapter={chapter}
    editable
    regenerating
    onChange={() => undefined}
    onRegenerate={() => undefined}
  />,
);
assert.match(running, /data-regenerating="true"/);
assert.match(running, /data-testid="framework-chapter-progress"/);
assert.match(running, /Updating this chapter/);
assert.match(running, /Only this chapter is being rewritten/);
assert.match(running, /several minutes/);
assert.doesNotMatch(running, />Regenerate chapter</);
assert.doesNotMatch(running, /Claude|Gamma/i);

console.log("FrameworkChapterView regenerate status tests passed");
