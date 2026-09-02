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

console.log("RecoveryBanner tests passed");
