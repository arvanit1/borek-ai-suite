import assert from "node:assert/strict";

import { customerBlockLabel, customerFieldLabel, customerStatusLabel } from "./frameworkLabels.js";
import {
  APPROVE_BUILD_LABEL,
  HUMAN_CONFIRM_LABEL,
  REVIEW_STATE_BLOCKING,
  REVIEW_STATE_READY,
  REVIEW_STATE_RECOMMENDED,
  attentionTone,
  blockingSignals,
  canApproveAndBuild,
  evidenceWarningText,
  isApprovalBlocked,
  isBlockingSignal,
  openItemText,
  reviewPayloadFromUnknown,
  reviewStateLabel,
} from "./frameworkReview.js";

const readyPayload = {
  review_state: REVIEW_STATE_READY,
  attention_signals: [
    {
      id: REVIEW_STATE_READY,
      severity: "info",
      message: "No blocking issues detected. Human approval is still required.",
      action: "Review the summary, then approve when ready.",
    },
  ],
  review_summary: {
    executive_summary: "Automate invoice matching.",
    key_pain_points: ["Manual matching"],
    key_requirements: ["ERP access"],
    target_outcomes: ["Under 2 days"],
    assumptions: [],
    open_questions: [],
    evidence_warnings: [],
    blocking_items: [],
    confirm_ready: true,
  },
};

const blockingPayload = {
  review_state: REVIEW_STATE_BLOCKING,
  attention_signals: [
    {
      id: REVIEW_STATE_BLOCKING,
      severity: "blocking",
      message: "AI used-for contradicts not-used-for.",
      action: "Fix the contradiction in chapter 6 before approval.",
      chapter_id: "6",
      fields: ["chapters.6.body.ai_split"],
    },
  ],
  review_summary: {
    confirm_ready: false,
    confirm_block_reason: "AI used-for contradicts not-used-for.",
    blocking_items: [{ kind: "confirm_gate", chapter_id: "6", message: "AI used-for contradicts not-used-for." }],
  },
};

const recommendedPayload = {
  review_state: REVIEW_STATE_RECOMMENDED,
  attention_signals: [
    {
      id: REVIEW_STATE_RECOMMENDED,
      severity: "warning",
      message: "Build-readiness is 72/100 with documented assumptions.",
      action: "Review assumptions in chapter 11 before approval.",
      chapter_id: "11",
    },
  ],
  review_summary: {
    confirm_ready: true,
    assumptions: [{ description: "Sample invoices have not been provided yet." }],
    blocking_items: [],
  },
};

assert.equal(isApprovalBlocked(readyPayload), false);
assert.equal(isApprovalBlocked(recommendedPayload), false);
assert.equal(isApprovalBlocked(blockingPayload), true);
assert.equal(isApprovalBlocked({ ...blockingPayload, attention_signals: [], review_state: "READY_TO_APPROVE", review_summary: { confirm_ready: false } }), true);
assert.equal(isBlockingSignal(blockingPayload.attention_signals[0]), true);
assert.equal(blockingSignals(blockingPayload.attention_signals).length, 1);
assert.equal(attentionTone(REVIEW_STATE_BLOCKING, blockingPayload.attention_signals), "blocking");
assert.equal(attentionTone(REVIEW_STATE_RECOMMENDED, recommendedPayload.attention_signals), "warning");
assert.equal(attentionTone(REVIEW_STATE_READY, readyPayload.attention_signals), "ready");
assert.equal(reviewStateLabel(REVIEW_STATE_BLOCKING), "Contradiction must be resolved");
assert.equal(reviewStateLabel(REVIEW_STATE_READY), "Ready to approve");

assert.equal(
  canApproveAndBuild({ editable: true, confirmed: false, humanConfirmed: true, blocked: false }),
  true,
);
assert.equal(
  canApproveAndBuild({ editable: true, confirmed: false, humanConfirmed: false, blocked: false }),
  false,
);
assert.equal(
  canApproveAndBuild({ editable: true, confirmed: false, humanConfirmed: true, blocked: true }),
  false,
);
assert.equal(
  canApproveAndBuild({ editable: false, confirmed: true, humanConfirmed: true, blocked: false }),
  false,
);

assert.equal(openItemText({ description: "Hours validated in workshop" }), "Hours validated in workshop");
assert.equal(
  evidenceWarningText({ chapter_id: "4", title: "Current process", message: "Chapter 4 has no source references." }),
  "Current process (chapter 4) has no cited sources.",
);

const extracted = reviewPayloadFromUnknown({
  review_summary: { headline: "Invoice match", executive_summary: "Match invoices." },
  attention: { review_state: REVIEW_STATE_READY, signals: readyPayload.attention_signals },
  attention_signals: readyPayload.attention_signals,
  review_state: REVIEW_STATE_READY,
});
assert.equal(extracted?.review_summary.headline, "Invoice match");
assert.equal(extracted?.review_state, REVIEW_STATE_READY);

const fromFrameworkJson = reviewPayloadFromUnknown({
  framework_json: {
    review_summary: { headline: "Nested" },
    attention: { review_state: REVIEW_STATE_RECOMMENDED, signals: recommendedPayload.attention_signals },
    attention_signals: recommendedPayload.attention_signals,
  },
});
assert.equal(fromFrameworkJson?.review_summary.headline, "Nested");
assert.equal(fromFrameworkJson?.review_state, REVIEW_STATE_RECOMMENDED);
assert.equal(reviewPayloadFromUnknown({ title: "No summary" }), null);

assert.equal(customerFieldLabel("source_refs"), "Cited sources");
assert.equal(customerFieldLabel("used_for"), "AI is used for");
assert.equal(customerFieldLabel("unknown_snake_field"), "Unknown Snake Field");
assert.equal(customerStatusLabel("confirmed"), "Approved");
assert.equal(customerBlockLabel("ai_split"), "Where AI is used");
assert.equal(APPROVE_BUILD_LABEL, "Approve & build presentation");
assert.match(HUMAN_CONFIRM_LABEL, /I have reviewed this customer story/);

console.log("frameworkReview tests passed");
