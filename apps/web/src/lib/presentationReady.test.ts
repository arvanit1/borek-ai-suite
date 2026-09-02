import assert from "node:assert/strict";

import {
  alternativeLayouts,
  formatGeneratedAt,
  formatLayoutLabel,
  presentationReadyTitle,
  slideCountLabel,
  versionLabel,
} from "./presentationReady.js";

assert.equal(formatLayoutLabel("PROCESS_FLOW_01"), "Process flow");
assert.equal(formatLayoutLabel("COVER_01"), "Cover");
assert.equal(formatLayoutLabel("CUSTOM_LAYOUT_02"), "Custom Layout");
assert.equal(alternativeLayouts("COVER_01").length, 0);
assert.equal(slideCountLabel(1), "1 slide");
assert.equal(slideCountLabel(12), "12 slides");
assert.equal(versionLabel(3), "Version 3");
assert.equal(versionLabel(null), null);
assert.equal(presentationReadyTitle(true), "Your presentation is ready");
assert.equal(formatGeneratedAt("not-a-date"), null);
assert.match(formatGeneratedAt("2026-09-02T06:11:00.000Z") ?? "", /2026/);

console.log("presentationReady tests passed");
