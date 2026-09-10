import type {
  JourneyStageEligibilityItem,
  JourneyStageEligibilityResponse,
  JourneyStageName,
} from "./api";
import firstContactOnlyFixture from "./fixtures/journey_stage_eligibility/first_contact_only.json";
import {
  JOURNEY_STAGE_CATALOG,
  JOURNEY_STAGE_LOCK_COPY,
  type JourneyStageCatalogEntry,
} from "./journeyStageConfig";

export const BT31_ELIGIBILITY_ERROR =
  "Journey-stage options must come from a BT-31 eligibility payload. The UI does not compute locks.";

export const NEW_CLIENT_ELIGIBILITY =
  firstContactOnlyFixture as JourneyStageEligibilityResponse;

export interface VisibleJourneyStage {
  id: JourneyStageName;
  label: string;
  description: string;
  startable: boolean;
  lockReason: string | null;
  nextAction: JourneyStageEligibilityItem["next_action"];
}

function isJourneyStageName(value: unknown): value is JourneyStageName {
  return value === "first_contact" || value === "deepening" || value === "concretisation";
}

export function requireEligibilityPayload(value: unknown): JourneyStageEligibilityResponse {
  if (!value || typeof value !== "object") {
    throw new Error(BT31_ELIGIBILITY_ERROR);
  }
  const payload = value as Partial<JourneyStageEligibilityResponse> & {
    completedDecks?: unknown;
    completedStages?: unknown;
    history?: unknown;
  };
  if (payload.completedDecks != null || payload.completedStages != null || payload.history != null) {
    throw new Error(BT31_ELIGIBILITY_ERROR);
  }
  if (payload.schema_version !== "1.0" || !Array.isArray(payload.stages) || payload.stages.length === 0) {
    throw new Error(BT31_ELIGIBILITY_ERROR);
  }
  return payload as JourneyStageEligibilityResponse;
}

export function lockCopyFor(
  item: Pick<JourneyStageEligibilityItem, "startable" | "next_action" | "reason">,
): string | null {
  if (item.startable) {
    return null;
  }
  if (item.next_action && JOURNEY_STAGE_LOCK_COPY[item.next_action]) {
    return JOURNEY_STAGE_LOCK_COPY[item.next_action];
  }
  return "This option is not available yet.";
}

export function visibleJourneyStages(
  eligibility: unknown,
  catalog: readonly JourneyStageCatalogEntry[] = JOURNEY_STAGE_CATALOG,
): VisibleJourneyStage[] {
  const payload = requireEligibilityPayload(eligibility);
  const byId = new Map(payload.stages.map((row) => [row.journey_stage, row]));
  return catalog.flatMap((entry) => {
    const row = byId.get(entry.id);
    if (!row) {
      return [];
    }
    return [
      {
        id: entry.id,
        label: entry.label,
        description: entry.description,
        startable: row.startable,
        lockReason: lockCopyFor(row),
        nextAction: row.next_action,
      },
    ];
  });
}

export function defaultStartableStage(
  eligibility: unknown,
  catalog: readonly JourneyStageCatalogEntry[] = JOURNEY_STAGE_CATALOG,
): JourneyStageName | null {
  return visibleJourneyStages(eligibility, catalog).find((row) => row.startable)?.id ?? null;
}

export function canSubmitJourneyStage(
  eligibility: unknown,
  selected: JourneyStageName | null,
  catalog: readonly JourneyStageCatalogEntry[] = JOURNEY_STAGE_CATALOG,
): selected is JourneyStageName {
  if (!selected || !isJourneyStageName(selected)) {
    return false;
  }
  return visibleJourneyStages(eligibility, catalog).some(
    (row) => row.id === selected && row.startable,
  );
}

export function journeyStageBusinessLabel(
  stage: string | null | undefined,
  catalog: readonly JourneyStageCatalogEntry[] = JOURNEY_STAGE_CATALOG,
): string | null {
  if (!stage) {
    return null;
  }
  return catalog.find((entry) => entry.id === stage)?.label ?? null;
}

export function eligibilityForOpportunity(
  payload: JourneyStageEligibilityResponse,
  opportunityId: string,
): JourneyStageEligibilityResponse {
  const required = requireEligibilityPayload(payload);
  if (required.opportunity_id !== opportunityId) {
    throw new Error("Eligibility belongs to a different opportunity and cannot unlock this client.");
  }
  return required;
}
