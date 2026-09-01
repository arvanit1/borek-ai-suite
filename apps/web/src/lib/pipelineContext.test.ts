import assert from "node:assert/strict";

import {
  clearOpportunityDraft,
  getCachedUploadSession,
  loadActiveOpportunity,
  loadOpportunityDraft,
  opportunityLabel,
  pipelineHref,
  rememberUploadSession,
  saveActiveOpportunity,
  saveActiveOpportunityId,
  saveOpportunityDraft,
  clearActiveOpportunity,
} from "./pipelineContext.js";

assert.equal(pipelineHref("/upload"), "/upload");
assert.equal(pipelineHref("/framework-review"), "/framework-review");
assert.equal(
  pipelineHref("/upload", "abc-123"),
  "/upload?opportunityId=abc-123",
);
assert.equal(
  pipelineHref("/framework-review", "abc-123"),
  "/framework-review?opportunityId=abc-123",
);
assert.equal(opportunityLabel({ client_name: "Acme", opportunity_name: "Q3" }), "Acme — Q3");

const memory = globalThis as typeof globalThis & { sessionStorage?: Storage };
const store = new Map<string, string>();
memory.sessionStorage = {
  getItem: (key: string) => store.get(key) ?? null,
  setItem: (key: string, value: string) => {
    store.set(key, value);
  },
  removeItem: (key: string) => {
    store.delete(key);
  },
  clear: () => store.clear(),
  key: () => null,
  length: 0,
};

saveActiveOpportunity({
  id: "opp-1",
  client_name: "Acme",
  opportunity_name: "Q3 rollout",
  department: "Finance",
  language: "en",
});
assert.equal(loadActiveOpportunity()?.id, "opp-1");
assert.equal(loadActiveOpportunity()?.client_name, "Acme");

saveActiveOpportunityId("opp-1");
assert.equal(loadActiveOpportunity()?.opportunity_name, "Q3 rollout");

saveOpportunityDraft({
  client_name: "Draft Co",
  opportunity_name: "Draft opp",
  department: "IT",
  language: "de",
});
assert.equal(loadOpportunityDraft()?.client_name, "Draft Co");
clearOpportunityDraft();
assert.equal(loadOpportunityDraft(), null);

rememberUploadSession({
  opportunity: loadActiveOpportunity(),
  queue: [],
  summary: "1 transcript ingested successfully.",
});
assert.equal(getCachedUploadSession().summary, "1 transcript ingested successfully.");
clearActiveOpportunity();
assert.equal(loadActiveOpportunity(), null);

console.log("pipelineContext tests passed");
