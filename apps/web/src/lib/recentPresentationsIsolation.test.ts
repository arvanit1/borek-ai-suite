import assert from "node:assert/strict";

import { buildRecentWorkItems, type RecentWorkSnapshot } from "./recentPresentations.js";

function snapshot(id: string, ownerId: string): RecentWorkSnapshot {
  return {
    opportunity: {
      id,
      client_name: `Client ${id}`,
      opportunity_name: `Opportunity ${id}`,
      created_by: ownerId,
      created_at: "2026-09-02T10:00:00Z",
      updated_at: "2026-09-02T10:00:00Z",
    },
    transcriptCount: 0,
    hasPlan: false,
  };
}

const cards = buildRecentWorkItems(
  [snapshot("owned", "user-1"), snapshot("foreign", "user-2")],
  "user-1",
);

assert.deepEqual(cards.map((card) => card.opportunityId), ["owned"]);
assert.ok(!cards.some((card) => card.clientName === "Client foreign"));

console.log("MS-24 recent presentation isolation tests passed");
