import assert from "node:assert/strict";

import {
  buildRecentWorkItems,
  formatRecentDate,
  latestActivityAt,
  selectRecentWorkJob,
  type RecentWorkSnapshot,
} from "./recentPresentations.js";

function snapshot(
  id: string,
  updatedAt: string,
  state: Partial<RecentWorkSnapshot> = {},
): RecentWorkSnapshot {
  return {
    opportunity: {
      id,
      client_name: `Client ${id}`,
      opportunity_name: `Opportunity ${id}`,
      created_by: "user-1",
      created_at: updatedAt,
      updated_at: updatedAt,
    },
    transcriptCount: 0,
    hasPlan: false,
    ...state,
  };
}

assert.deepEqual(buildRecentWorkItems([]), []);

const mixed = buildRecentWorkItems([
  snapshot("draft", "2026-08-28T09:00:00Z"),
  snapshot("analysis", "2026-08-29T09:00:00Z", { transcriptCount: 2 }),
  snapshot("review", "2026-08-30T09:00:00Z", { frameworkStatus: "in_review" }),
  snapshot("building", "2026-08-31T09:00:00Z", { presentationId: "presentation-1" }),
  snapshot("failed", "2026-09-01T09:00:00Z", {
    job: { job_type: "presentation_generation", status: "FAILED", current_stage: "FAILED" },
  }),
]);

assert.deepEqual(
  mixed.map((item) => item.statusLabel),
  ["Needs attention", "Building presentation", "Needs review", "Analyzing", "Draft"],
);
assert.equal(mixed[0]?.actionHref, "/deck-center?opportunityId=failed");
assert.equal(mixed[1]?.actionHref, "/deck-center?opportunityId=building");
assert.equal(mixed[2]?.actionHref, "/framework-review?opportunityId=review");
assert.equal(mixed[3]?.actionHref, "/framework-review?opportunityId=analysis");

const ready = buildRecentWorkItems([
  snapshot("ready", "2026-09-01T10:00:00Z", {
    presentationId: "presentation-ready",
    presentationName: "Customer proposal",
    deck: { pptx_download_url: "/presentations/presentation-ready/download/pptx" },
  }),
])[0]!;

assert.equal(ready.statusLabel, "Ready");
assert.equal(ready.actionLabel, "Open");
assert.equal(ready.actionHref, "/deck-center?opportunityId=ready");
assert.equal(ready.downloadPath, "/presentations/presentation-ready/download/pptx");

const running = buildRecentWorkItems([
  snapshot("running", "2026-09-01T11:00:00Z", {
    hasPlan: true,
    job: {
      job_type: "presentation_generation",
      status: "RUNNING",
      current_stage: "PPTX_RENDERING",
    },
  }),
])[0]!;
assert.equal(running.statusLabel, "Building presentation");
assert.equal(running.actionHref, "/deck-center?opportunityId=running");
assert.equal(running.downloadPath, undefined);

const runningFramework = buildRecentWorkItems([
  snapshot("running-framework", "2026-09-01T11:30:00Z", {
    job: {
      job_type: "framework_generation",
      status: "QUEUED",
      current_stage: "QUEUED",
    },
  }),
])[0]!;
assert.equal(runningFramework.statusLabel, "Analyzing");
assert.equal(
  runningFramework.actionHref,
  "/framework-review?opportunityId=running-framework",
);

const readyDuringFrameworkExport = buildRecentWorkItems([
  snapshot("ready-export", "2026-09-01T11:45:00Z", {
    presentationId: "presentation-ready-export",
    deck: { pptx_download_url: "/presentations/presentation-ready-export/download/pptx" },
    job: {
      job_type: "framework_render",
      status: "RUNNING",
      current_stage: "FRAMEWORK_SYNTHESIZING",
    },
  }),
])[0]!;
assert.equal(readyDuringFrameworkExport.statusLabel, "Ready");
assert.equal(readyDuringFrameworkExport.actionHref, "/deck-center?opportunityId=ready-export");
assert.ok(readyDuringFrameworkExport.downloadPath);

const planning = buildRecentWorkItems([
  snapshot("planning", "2026-09-01T11:50:00Z", {
    frameworkStatus: "confirmed",
    job: {
      job_type: "presentation_planning",
      status: "RUNNING",
      current_stage: "PRESENTATION_PLANNING",
      auto_continue: true,
    },
  }),
])[0]!;
assert.equal(planning.statusLabel, "Building presentation");
assert.equal(planning.actionHref, "/framework-review?opportunityId=planning");

const manualPlanning = buildRecentWorkItems([
  snapshot("manual-planning", "2026-09-01T11:55:00Z", {
    frameworkStatus: "confirmed",
    job: {
      job_type: "presentation_planning",
      status: "RUNNING",
      current_stage: "PRESENTATION_PLANNING",
      auto_continue: false,
    },
  }),
])[0]!;
assert.equal(manualPlanning.actionHref, "/plan-preview?opportunityId=manual-planning");

const failedAutomaticPlanning = buildRecentWorkItems([
  snapshot("failed-auto-planning", "2026-09-01T11:57:00Z", {
    frameworkStatus: "confirmed",
    job: {
      job_type: "presentation_planning",
      status: "FAILED",
      current_stage: "FAILED",
      auto_continue: true,
    },
  }),
])[0]!;
assert.equal(failedAutomaticPlanning.statusLabel, "Needs attention");
assert.equal(
  failedAutomaticPlanning.actionHref,
  "/framework-review?opportunityId=failed-auto-planning",
);

assert.equal(
  selectRecentWorkJob([
    {
      job_id: "framework-render-job",
      job_type: "framework_render",
      status: "RUNNING",
      current_stage: "FRAMEWORK_SYNTHESIZING",
      started_at: "2026-09-01T12:00:00Z",
    },
    {
      job_id: "presentation-job",
      job_type: "presentation_generation",
      status: "RUNNING",
      current_stage: "SLIDE_GENERATING",
      started_at: "2026-09-01T11:59:00Z",
    },
  ])?.job_type,
  "presentation_generation",
);

const foreign = snapshot("cached-foreign", "2026-09-01T14:00:00Z");
foreign.opportunity.created_by = "user-2";
const authenticatedRows = buildRecentWorkItems(
  [
    snapshot("owned-1", "2026-09-01T12:00:00Z"),
    snapshot("owned-2", "2026-09-01T13:00:00Z"),
    foreign,
  ],
  "user-1",
);
assert.deepEqual(authenticatedRows.map((item) => item.opportunityId), ["owned-2", "owned-1"]);
assert.ok(!authenticatedRows.some((item) => item.opportunityId === "cached-foreign"));

const activitySorted = buildRecentWorkItems([
  snapshot("new-opportunity", "2026-09-01T13:00:00Z"),
  snapshot("recently-rendered", "2026-08-20T13:00:00Z", {
    activityAt: "2026-09-01T14:00:00Z",
  }),
]);
assert.deepEqual(
  activitySorted.map((item) => item.opportunityId),
  ["recently-rendered", "new-opportunity"],
);
assert.equal(
  latestActivityAt(
    "2026-08-20T13:00:00Z",
    undefined,
    "2026-09-01T14:00:00Z",
    "invalid",
  ),
  "2026-09-01T14:00:00Z",
);

assert.equal(formatRecentDate("2026-09-01T23:30:00-05:00"), "2 Sep 2026");
assert.equal(formatRecentDate("invalid"), "Date unavailable");

console.log("MS-24 recent presentations tests passed");
