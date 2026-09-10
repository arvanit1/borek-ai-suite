import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import type { JourneyStageEligibilityResponse } from "./api.js";
import { JOURNEY_STAGE_CATALOG, catalogWithoutStage } from "./journeyStageConfig.js";
import {
  BT31_ELIGIBILITY_ERROR,
  NEW_CLIENT_ELIGIBILITY,
  canSubmitJourneyStage,
  defaultStartableStage,
  eligibilityForOpportunity,
  requireEligibilityPayload,
  visibleJourneyStages,
} from "./journeyStageEligibility.js";

const here = dirname(fileURLToPath(import.meta.url));
const contractFixture = JSON.parse(
  readFileSync(
    resolve(
      here,
      "../../../../packages/contracts/fixtures/journey_stage_eligibility/first_contact_only.json",
    ),
    "utf8",
  ),
) as JourneyStageEligibilityResponse;

assert.deepEqual(NEW_CLIENT_ELIGIBILITY, contractFixture);

const deepeningUnlocked: JourneyStageEligibilityResponse = {
  schema_version: "1.0",
  opportunity_id: "opp-deepening",
  requested_journey_stage: "deepening",
  startable: true,
  prerequisite_stage: "first_contact",
  prior_stage_presentation_version_id: "ver-first",
  reason: null,
  next_action: null,
  stages: [
    {
      journey_stage: "first_contact",
      startable: true,
      prerequisite_stage: null,
      prior_stage_presentation_version_id: null,
      reason: null,
      next_action: null,
    },
    {
      journey_stage: "deepening",
      startable: true,
      prerequisite_stage: "first_contact",
      prior_stage_presentation_version_id: "ver-first",
      reason: null,
      next_action: null,
    },
    {
      journey_stage: "concretisation",
      startable: false,
      prerequisite_stage: "deepening",
      prior_stage_presentation_version_id: null,
      reason: "NO_COMPLETED_PREREQUISITE",
      next_action: "complete_deepening",
    },
  ],
};

const concretisationUnlocked: JourneyStageEligibilityResponse = {
  ...deepeningUnlocked,
  opportunity_id: "opp-concretisation",
  requested_journey_stage: "concretisation",
  prior_stage_presentation_version_id: "ver-deepening",
  stages: deepeningUnlocked.stages.map((row) =>
    row.journey_stage === "concretisation"
      ? {
          ...row,
          startable: true,
          prior_stage_presentation_version_id: "ver-deepening",
          reason: null,
          next_action: null,
        }
      : row,
  ),
};

assert.equal(defaultStartableStage(NEW_CLIENT_ELIGIBILITY), "first_contact");
assert.equal(canSubmitJourneyStage(NEW_CLIENT_ELIGIBILITY, "first_contact"), true);
assert.equal(canSubmitJourneyStage(NEW_CLIENT_ELIGIBILITY, "deepening"), false);
assert.equal(canSubmitJourneyStage(NEW_CLIENT_ELIGIBILITY, "concretisation"), false);

const newClientOptions = visibleJourneyStages(NEW_CLIENT_ELIGIBILITY);
assert.deepEqual(
  newClientOptions.map((row) => [row.label, row.startable, row.lockReason]),
  [
    ["First contact", true, null],
    ["Deepening", false, "Generate a First contact pack for this client first."],
    ["Concretisation", false, "Generate a Deepening pitch for this client first."],
  ],
);

const deepeningOptions = visibleJourneyStages(deepeningUnlocked);
assert.equal(deepeningOptions.find((row) => row.id === "deepening")?.startable, true);
assert.equal(canSubmitJourneyStage(deepeningUnlocked, "deepening"), true);
assert.equal(canSubmitJourneyStage(deepeningUnlocked, "concretisation"), false);
assert.equal(
  deepeningOptions.find((row) => row.id === "concretisation")?.lockReason,
  "Generate a Deepening pitch for this client first.",
);

const allOpen = visibleJourneyStages(concretisationUnlocked);
assert.equal(allOpen.every((row) => row.startable), true);
assert.equal(canSubmitJourneyStage(concretisationUnlocked, "concretisation"), true);

assert.throws(() => requireEligibilityPayload({ completedDecks: ["first_contact"] }), {
  message: BT31_ELIGIBILITY_ERROR,
});
assert.throws(() => visibleJourneyStages({ completedStages: ["first_contact"] }), {
  message: BT31_ELIGIBILITY_ERROR,
});
assert.throws(() => visibleJourneyStages({ history: [{ client: "other", stage: "first_contact" }] }), {
  message: BT31_ELIGIBILITY_ERROR,
});
assert.throws(() => requireEligibilityPayload({ schema_version: "1.0" }), {
  message: BT31_ELIGIBILITY_ERROR,
});

assert.deepEqual(
  eligibilityForOpportunity(deepeningUnlocked, "opp-deepening").opportunity_id,
  "opp-deepening",
);
assert.throws(() => eligibilityForOpportunity(deepeningUnlocked, "opp-other"), {
  message: /different opportunity/,
});

const otherClient = {
  ...NEW_CLIENT_ELIGIBILITY,
  opportunity_id: "opp-other",
};
const isolated = visibleJourneyStages(otherClient);
assert.equal(isolated.find((row) => row.id === "deepening")?.startable, false);
assert.notEqual(otherClient.opportunity_id, deepeningUnlocked.opportunity_id);

const withoutDeepening = visibleJourneyStages(
  NEW_CLIENT_ELIGIBILITY,
  catalogWithoutStage(JOURNEY_STAGE_CATALOG, "deepening"),
);
assert.deepEqual(
  withoutDeepening.map((row) => row.label),
  ["First contact", "Concretisation"],
);
assert.equal(withoutDeepening.find((row) => row.id === "first_contact")?.startable, true);
assert.equal(withoutDeepening.find((row) => row.id === "concretisation")?.startable, false);
assert.equal(
  withoutDeepening.find((row) => row.id === "concretisation")?.lockReason,
  "Generate a Deepening pitch for this client first.",
);
assert.equal(
  canSubmitJourneyStage(
    NEW_CLIENT_ELIGIBILITY,
    "first_contact",
    catalogWithoutStage(JOURNEY_STAGE_CATALOG, "deepening"),
  ),
  true,
);
assert.equal(
  canSubmitJourneyStage(
    NEW_CLIENT_ELIGIBILITY,
    "concretisation",
    catalogWithoutStage(JOURNEY_STAGE_CATALOG, "deepening"),
  ),
  false,
);

for (const htmlSource of [
  JSON.stringify(NEW_CLIENT_ELIGIBILITY),
  JSON.stringify(newClientOptions),
]) {
  assert.doesNotMatch(htmlSource, /borek-branded-standard|gamma|template_id/i);
}

console.log("journeyStageEligibility tests passed");
