import assert from "node:assert/strict";

import {
  bindSelectedJourneyStage,
  clearSelectedJourneyStage,
  continueHref,
  journeyStageForGenerate,
  loadSelectedJourneyStage,
  saveSelectedJourneyStage,
} from "./journeyStageSelection.js";

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

clearSelectedJourneyStage();
assert.equal(loadSelectedJourneyStage(), null);
assert.equal(journeyStageForGenerate("opp-1"), undefined);

saveSelectedJourneyStage("first_contact");
assert.deepEqual(loadSelectedJourneyStage(), {
  journeyStage: "first_contact",
  opportunityId: null,
});
assert.equal(journeyStageForGenerate(), "first_contact");
assert.equal(journeyStageForGenerate("opp-1"), "first_contact");

bindSelectedJourneyStage("opp-1");
assert.deepEqual(loadSelectedJourneyStage(), {
  journeyStage: "first_contact",
  opportunityId: "opp-1",
});
assert.equal(journeyStageForGenerate("opp-1"), "first_contact");
assert.equal(journeyStageForGenerate("opp-other"), undefined);

saveSelectedJourneyStage("deepening", "opp-1");
assert.equal(journeyStageForGenerate("opp-1"), "deepening");

assert.equal(continueHref(null), "/upload?new=1");
assert.equal(continueHref("opp-1"), "/upload?opportunityId=opp-1");

clearSelectedJourneyStage();
assert.equal(loadSelectedJourneyStage(), null);

console.log("journeyStageSelection tests passed");
