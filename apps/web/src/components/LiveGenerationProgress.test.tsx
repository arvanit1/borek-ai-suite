import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { buildJobProgressView, type JobProgressSnapshot } from "../lib/jobProgress.js";
import { LiveGenerationProgress } from "./LiveGenerationProgress.js";

const STARTED_AT = "2026-09-02T10:00:00.000Z";
const NOW = Date.parse(STARTED_AT) + 102_000;

function snapshot(overrides: Partial<JobProgressSnapshot> = {}): JobProgressSnapshot {
  return {
    jobId: "job-1",
    jobType: "presentation_generation",
    status: "RUNNING",
    currentStage: "SLIDE_VALIDATING",
    startedAt: STARTED_AT,
    createdAt: STARTED_AT,
    completedAt: null,
    error: null,
    ...overrides,
  };
}

function render(
  input: Parameters<typeof buildJobProgressView>[0],
  nowMs = NOW,
): string {
  const view = buildJobProgressView(input);
  assert.ok(view, "expected a progress view");
  return renderToStaticMarkup(<LiveGenerationProgress view={view} nowMs={nowMs} />);
}

// Deck generation shows completed, current, and upcoming stages with real labels.
{
  const html = render({ snapshot: snapshot(), plannedSlideCount: 12 });
  assert.match(html, /data-testid="live-generation-progress"/);
  assert.match(html, /data-status="RUNNING"/);
  assert.match(html, /data-step="SLIDE_GENERATING" data-state="complete"/);
  assert.match(html, /data-step="SLIDE_VALIDATING" data-state="current"/);
  assert.match(html, /data-step="PPTX_RENDERING" data-state="upcoming"/);
  assert.match(html, /data-step="GAMMA_RENDERING" data-state="upcoming"/);
  assert.match(html, /data-step="ARTIFACT_FILING" data-state="upcoming"/);
  assert.match(html, /aria-current="step"/);
  assert.match(html, /Preparing presentation structure/);
  assert.match(html, /Generating slide content/);
  assert.match(html, /Validating slides/);
  assert.match(html, /Rendering PowerPoint\/PDF/);
  assert.match(html, /Building branded presentation/);
  assert.match(html, /Archiving generated files/);
  assert.match(html, /Preparing preview/);
  assert.match(html, /12 slides planned/);

  // Real elapsed time, no percentage, no ETA, no raw enum copy.
  assert.match(html, /Elapsed 1m 42s/);
  assert.doesNotMatch(html, /%/);
  assert.doesNotMatch(html, /remaining|minutes left|\bETA\b/i);
  assert.doesNotMatch(html, />[^<]*SLIDE_VALIDATING[^<]*</);
  assert.doesNotMatch(html, /progressbar/);
}

// Framework generation uses Framework stages only.
{
  const html = render({
    snapshot: snapshot({
      jobType: "framework_generation",
      currentStage: "KNOWLEDGE_EXTRACTING",
    }),
  });
  assert.match(html, /data-phase="framework"/);
  assert.match(html, /data-step="TRANSCRIPT_PROCESSING" data-state="complete"/);
  assert.match(html, /data-step="KNOWLEDGE_EXTRACTING" data-state="current"/);
  assert.doesNotMatch(html, /Generating slide content/);
}

// Reconnect at PPTX_RENDERING renders the rendering stage, not the first stage.
{
  const html = render({ snapshot: snapshot({ currentStage: "PPTX_RENDERING" }) });
  assert.match(html, /data-step="PPTX_RENDERING" data-state="current"/);
  assert.match(
    html,
    /data-testid="live-progress-headline">Rendering PowerPoint\/PDF</,
  );
}

// Planning → generation handoff renders a neutral waiting state.
{
  const html = render({
    snapshot: snapshot({
      jobType: "presentation_planning",
      status: "COMPLETED",
      currentStage: "COMPLETED",
    }),
    handoff: true,
  });
  assert.match(html, /Starting presentation generation/);
  assert.doesNotMatch(html, /failed|error/i);
  assert.doesNotMatch(html, /data-state="failed"/);
}

// A failed backend job stops at the failing stage and surfaces the real message.
{
  const html = render({
    snapshot: snapshot({
      status: "FAILED",
      currentStage: "PPTX_RENDERING",
      error: {
        code: "RENDERER_FAILED",
        message: "The renderer could not produce the PowerPoint file.",
        stage: "PPTX_RENDERING",
        retryable: true,
      },
    }),
  });
  assert.match(html, /data-step="PPTX_RENDERING" data-state="failed"/);
  assert.match(html, /data-step="PREVIEW_RENDERING" data-state="upcoming"/);
  assert.match(html, /The renderer could not produce the PowerPoint file\./);
}

// A job without timestamps simply omits the elapsed counter.
{
  const html = render({
    snapshot: snapshot({ status: "QUEUED", currentStage: "QUEUED", startedAt: null, createdAt: null }),
  });
  assert.match(html, /Waiting to start/);
  assert.doesNotMatch(html, /Elapsed/);
}

console.log("LiveGenerationProgress tests passed");
