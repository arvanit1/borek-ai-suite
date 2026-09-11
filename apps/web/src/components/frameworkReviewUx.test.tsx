import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { WorkflowActionBar } from "./WorkflowActionBar.js";

const actionBarHtml = renderToStaticMarkup(
  <WorkflowActionBar
    backHref="/upload?opportunityId=example"
    backLabel="Back to intake"
    contextLabel="Current step"
    context={<strong>Customer story review</strong>}
  >
    <button type="button">Approve &amp; build presentation</button>
  </WorkflowActionBar>,
);

assert.match(actionBarHtml, /aria-label="Workflow actions"/);
assert.match(actionBarHtml, /Back to intake/);
assert.match(actionBarHtml, /Current step/);
assert.match(actionBarHtml, /Approve &amp; build presentation/);

const panelSource = readFileSync(
  fileURLToPath(new URL("./FrameworkReviewPanel.tsx", import.meta.url)),
  "utf8",
);
assert.doesNotMatch(panelSource, /PipelineStepper|framework-sidebar|Review all 14 chapters/);
assert.match(panelSource, /framework-top-approve-button/);
assert.match(panelSource, /framework-chapter-list/);
assert.match(panelSource, /aria-expanded={isOpen}/);
assert.match(panelSource, /isOpen \? closeChapter\(item\.chapterId\) : openChapter\(item\.chapterId\)/);
assert.equal(panelSource.match(/<FrameworkChapterView/g)?.length, 1);
assert.match(panelSource, /Previous chapter/);
assert.match(panelSource, /Next chapter/);

const summarySource = readFileSync(
  fileURLToPath(new URL("./FrameworkReviewSummary.tsx", import.meta.url)),
  "utf8",
);
assert.match(summarySource, /framework-executive-summary/);
assert.match(summarySource, /framework-summary-details/);
assert.match(summarySource, /View summary details/);

console.log("Framework review UX tests passed");
