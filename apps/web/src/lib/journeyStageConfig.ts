import type { JourneyStageName } from "./api";

export interface JourneyStageCatalogEntry {
  id: JourneyStageName;
  label: string;
  description: string;
}

/**
 * Visible journey options. Removing Deepening is a config change here,
 * not a rewrite of the selector. BT-31 still owns the lock flags.
 */
export const JOURNEY_STAGE_CATALOG: readonly JourneyStageCatalogEntry[] = [
  {
    id: "first_contact",
    label: "First contact",
    description: "A generic Borek information pack for a first conversation.",
  },
  {
    id: "deepening",
    label: "Deepening",
    description: "A tailored pitch that continues from the First contact pack.",
  },
  {
    id: "concretisation",
    label: "Concretisation",
    description: "A priced proposal that continues from the Deepening pitch.",
  },
];

export const NEW_CLIENT_SCOPE = "new-client";

export const JOURNEY_STAGE_LOCK_COPY: Record<
  NonNullable<import("./api").JourneyStageEligibilityItem["next_action"]>,
  string
> = {
  complete_first_contact: "Generate a First contact pack for this client first.",
  complete_deepening: "Generate a Deepening pitch for this client first.",
  regenerate_prior_stage: "Regenerate the previous pack for this client first.",
  select_journey_stage: "Choose an available option to continue.",
};

export function catalogWithoutStage(
  catalog: readonly JourneyStageCatalogEntry[],
  stageId: JourneyStageName,
): JourneyStageCatalogEntry[] {
  return catalog.filter((entry) => entry.id !== stageId);
}
