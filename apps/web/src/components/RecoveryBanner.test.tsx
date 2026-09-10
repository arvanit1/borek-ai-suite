import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { RecoveryBanner } from "./RecoveryBanner.js";

const html = renderToStaticMarkup(
  <RecoveryBanner
    notice={{
      category: "TERMINAL_FAILURE",
      title: "We could not complete your presentation",
      message: "Your saved work remains available.",
      action: { kind: "RETRY", label: "Try again" },
      technical: {
        code: "RENDERER_FAILED",
        stage: "PPTX_RENDERING",
        jobId: "job-secret",
        message: "C:\\internal\\renderer failed",
      },
    }}
    onAction={() => undefined}
  />,
);

assert.equal((html.match(/data-testid="recovery-banner"/g) ?? []).length, 1);
assert.equal((html.match(/data-testid="recovery-action"/g) ?? []).length, 1);
assert.match(html, /data-recovery-category="TERMINAL_FAILURE"/);
assert.match(html, /<details class="recovery-details">/);
assert.doesNotMatch(html, /<details[^>]* open/);
assert.ok(html.indexOf("<details") < html.indexOf("job-secret"));
assert.ok(html.indexOf("<details") < html.indexOf("internal"));

const generateHtml = renderToStaticMarkup(
  <RecoveryBanner
    notice={{
      category: "TERMINAL_FAILURE",
      title: "We could not complete your framework",
      message: "The customer story could not be finished. You can generate it again from the same transcripts.",
      action: { kind: "GENERATE", label: "Generate again" },
      technical: {
        code: "FRAMEWORK_GENERATION_FAILED",
        message: "ch.4 today_vs_agent: Chapter 4 must compare today vs with the agent.",
      },
    }}
    onAction={() => undefined}
  />,
);
assert.match(generateHtml, />Generate again</);
assert.doesNotMatch(generateHtml, /href=/);
assert.match(generateHtml, /ch\.4 today_vs_agent/);
assert.ok(generateHtml.indexOf("<details") < generateHtml.indexOf("today_vs_agent"));

console.log("RecoveryBanner tests passed");
