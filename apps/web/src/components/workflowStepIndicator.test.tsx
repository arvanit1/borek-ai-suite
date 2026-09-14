import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { WorkflowStepIndicator } from "./WorkflowStepIndicator.js";

const html = renderToStaticMarkup(<WorkflowStepIndicator currentStep={3} />);
assert.match(html, /aria-label="Presentation steps"/);
assert.match(html, /Intake/);
assert.match(html, /Customer story/);
assert.match(html, /Plan/);
assert.match(html, /Presentation/);
assert.match(html, /aria-current="step"/);
assert.doesNotMatch(html, /<a /);

const current = html.match(/is-current[\s\S]*?workflow-step-label">([^<]+)/);
assert.equal(current?.[1], "Plan");

for (const name of [
  "TranscriptUploadPanel.tsx",
  "FrameworkReviewPanel.tsx",
  "PlanPreviewPanel.tsx",
  "DeckCenterPanel.tsx",
]) {
  const source = readFileSync(fileURLToPath(new URL(`./${name}`, import.meta.url)), "utf8");
  assert.match(source, /WorkflowStepIndicator/, name);
  assert.match(source, /WorkflowActionBar/, name);
  assert.doesNotMatch(source, /PipelineStepper/, name);
}

const planSource = readFileSync(
  fileURLToPath(new URL("./PlanPreviewPanel.tsx", import.meta.url)),
  "utf8",
);
const deckSource = readFileSync(
  fileURLToPath(new URL("./DeckCenterPanel.tsx", import.meta.url)),
  "utf8",
);
assert.doesNotMatch(planSource, /upload-sidebar|Step 3 of 4/);
assert.doesNotMatch(deckSource, /upload-sidebar|Step 4 of 4/);

console.log("Workflow step indicator tests passed");
