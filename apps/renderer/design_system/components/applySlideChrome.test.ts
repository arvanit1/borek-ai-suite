/** Shared slide-chrome leftover-placeholder and logo-variant checks. */

import assert from "node:assert/strict";

import {
  leftoverPlaceholdersForSlide,
  logoVariantForSlide,
  usesClosingMaster,
} from "./applySlideChrome.js";
import {
  MASTER_CLOSING_CHECKLIST_PLACEHOLDER,
  MASTER_CLOSING_STEPS_PLACEHOLDER,
} from "../masters/MASTER_CLOSING.js";
import { MASTER_CONTENT_LABEL_PLACEHOLDER } from "../masters/MASTER_CONTENT.js";

assert.equal(logoVariantForSlide({ opportunityTitle: "T", layoutId: "COVER_01" }), "dark");
assert.equal(
  logoVariantForSlide({
    opportunityTitle: "T",
    layoutId: "COMPLIANCE_01",
    darkBackground: true,
  }),
  "dark",
);
assert.equal(logoVariantForSlide({ opportunityTitle: "T", layoutId: "PROCESS_FLOW_01" }), "light");
assert.equal(logoVariantForSlide({ opportunityTitle: "T", layoutId: "TIMELINE_01" }), "light");

assert.equal(
  usesClosingMaster({ opportunityTitle: "T", layoutId: "COMPLIANCE_01", darkBackground: true }),
  true,
);
assert.equal(
  usesClosingMaster({ opportunityTitle: "T", layoutId: "PROCESS_FLOW_01", darkBackground: true }),
  false,
);

assert.deepEqual(
  leftoverPlaceholdersForSlide({ opportunityTitle: "T", layoutId: "PROCESS_FLOW_01" }),
  [MASTER_CONTENT_LABEL_PLACEHOLDER],
);
assert.deepEqual(
  leftoverPlaceholdersForSlide({
    opportunityTitle: "T",
    layoutId: "TIMELINE_01",
    sectionLabel: "COMPLEXITY & EFFORT",
  }),
  [],
);
assert.deepEqual(
  leftoverPlaceholdersForSlide({
    opportunityTitle: "T",
    layoutId: "COMPLIANCE_01",
    sectionLabel: "SECURITY",
    darkBackground: true,
  }),
  [MASTER_CLOSING_CHECKLIST_PLACEHOLDER, MASTER_CLOSING_STEPS_PLACEHOLDER],
);

process.stdout.write("slide chrome leftover and logo-variant checks passed\n");
