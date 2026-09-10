import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { JourneyStageEligibilityResponse } from "../lib/api.js";
import { JOURNEY_STAGE_CATALOG, catalogWithoutStage } from "../lib/journeyStageConfig.js";
import { NEW_CLIENT_ELIGIBILITY } from "../lib/journeyStageEligibility.js";
import { JourneyStageChoice, JourneyStageSelector } from "./JourneyStageSelector.js";

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
  stages: deepeningUnlocked.stages.map((row) =>
    row.journey_stage === "concretisation"
      ? { ...row, startable: true, reason: null, next_action: null }
      : row,
  ),
};

function radioDisabled(html: string, label: string): boolean {
  const block = html.split("<label").find((part) => part.includes(label));
  assert.ok(block, `missing option ${label}`);
  return /disabled/.test(block);
}

function radioChecked(html: string, label: string): boolean {
  const block = html.split("<label").find((part) => part.includes(label));
  assert.ok(block, `missing option ${label}`);
  return /checked/.test(block);
}

const newClientHtml = renderToStaticMarkup(
  <JourneyStageSelector
    eligibility={NEW_CLIENT_ELIGIBILITY}
    selected="first_contact"
    onSelect={() => undefined}
  />,
);
assert.match(newClientHtml, /First contact/);
assert.match(newClientHtml, /Deepening/);
assert.match(newClientHtml, /Concretisation/);
assert.match(newClientHtml, /Generate a First contact pack for this client first/);
assert.match(newClientHtml, /Generate a Deepening pitch for this client first/);
assert.equal(radioChecked(newClientHtml, "First contact"), true);
assert.equal(radioDisabled(newClientHtml, "First contact"), false);
assert.equal(radioDisabled(newClientHtml, "Deepening"), true);
assert.equal(radioDisabled(newClientHtml, "Concretisation"), true);
const newClientVisible = newClientHtml.replace(/<input[^>]*>/g, "");
assert.doesNotMatch(newClientVisible, /first_contact|template_id|\bgamma\b/);

const deepeningHtml = renderToStaticMarkup(
  <JourneyStageSelector
    eligibility={deepeningUnlocked}
    selected="deepening"
    onSelect={() => undefined}
  />,
);
assert.equal(radioDisabled(deepeningHtml, "Deepening"), false);
assert.equal(radioChecked(deepeningHtml, "Deepening"), true);
assert.equal(radioDisabled(deepeningHtml, "Concretisation"), true);

const openHtml = renderToStaticMarkup(
  <JourneyStageSelector
    eligibility={concretisationUnlocked}
    selected="concretisation"
    onSelect={() => undefined}
  />,
);
assert.equal(radioDisabled(openHtml, "Concretisation"), false);
assert.equal(radioChecked(openHtml, "Concretisation"), true);

assert.throws(() =>
  renderToStaticMarkup(
    <JourneyStageSelector
      eligibility={{ completedDecks: ["first_contact"] } as never}
      selected="first_contact"
      onSelect={() => undefined}
    />,
  ),
);

const twoStageHtml = renderToStaticMarkup(
  <JourneyStageSelector
    eligibility={NEW_CLIENT_ELIGIBILITY}
    selected="first_contact"
    onSelect={() => undefined}
    catalog={catalogWithoutStage(JOURNEY_STAGE_CATALOG, "deepening")}
  />,
);
assert.match(twoStageHtml, /First contact/);
assert.match(twoStageHtml, /Concretisation/);
assert.doesNotMatch(twoStageHtml, />Deepening</);
assert.equal(radioDisabled(twoStageHtml, "Concretisation"), true);

const choice = renderToStaticMarkup(<JourneyStageChoice stage="first_contact" />);
assert.match(choice, /This presentation: First contact/);
assert.doesNotMatch(choice, /first_contact|template_id|\bgamma\b/);

console.log("journeyStageSelector tests passed");
