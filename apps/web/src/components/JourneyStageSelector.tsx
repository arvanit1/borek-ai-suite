"use client";

import React from "react";

import type { JourneyStageEligibilityResponse, JourneyStageName } from "@/lib/api";
import { JOURNEY_STAGE_CATALOG, type JourneyStageCatalogEntry } from "@/lib/journeyStageConfig";
import { requireEligibilityPayload, visibleJourneyStages } from "@/lib/journeyStageEligibility";

interface JourneyStageSelectorProps {
  eligibility: JourneyStageEligibilityResponse;
  selected: JourneyStageName | null;
  onSelect: (stage: JourneyStageName) => void;
  catalog?: readonly JourneyStageCatalogEntry[];
  disabled?: boolean;
  name?: string;
}

export function JourneyStageSelector({
  eligibility,
  selected,
  onSelect,
  catalog = JOURNEY_STAGE_CATALOG,
  disabled = false,
  name = "journey-stage",
}: JourneyStageSelectorProps) {
  const payload = requireEligibilityPayload(eligibility);
  const options = visibleJourneyStages(payload, catalog);

  return (
    <fieldset className="journey-stage-selector" data-testid="journey-stage-selector">
      <legend className="sr-only">Which output do you want to produce?</legend>
      <div className="journey-stage-options">
        {options.map((option) => {
          const locked = !option.startable;
          return (
            <label
              key={option.id}
              className={`journey-stage-option${locked ? " is-locked" : ""}${
                selected === option.id ? " is-selected" : ""
              }`}
            >
              <input
                type="radio"
                name={name}
                value={option.id}
                checked={selected === option.id}
                disabled={locked || disabled}
                onChange={() => {
                  if (!locked) {
                    onSelect(option.id);
                  }
                }}
              />
              <span className="journey-stage-option-body">
                <span className="journey-stage-option-label">{option.label}</span>
                <span className="journey-stage-option-description">{option.description}</span>
                {locked && option.lockReason ? (
                  <span className="journey-stage-option-lock">{option.lockReason}</span>
                ) : null}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

export function JourneyStageChoice({ stage }: { stage: JourneyStageName | null }) {
  const label = JOURNEY_STAGE_CATALOG.find((entry) => entry.id === stage)?.label;
  if (!label) {
    return null;
  }
  return (
    <p className="journey-stage-choice" data-testid="journey-stage-choice">
      This presentation: {label}
    </p>
  );
}
