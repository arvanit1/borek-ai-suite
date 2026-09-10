import type { JourneyStageName } from "./api";

const SELECTION_KEY = "borek.selectedJourneyStage";

export interface StoredJourneyStageSelection {
  journeyStage: JourneyStageName;
  opportunityId: string | null;
}

function getSessionStorage(): Storage | null {
  try {
    const storage = globalThis.sessionStorage;
    return storage ?? null;
  } catch {
    return null;
  }
}

function isJourneyStageName(value: unknown): value is JourneyStageName {
  return value === "first_contact" || value === "deepening" || value === "concretisation";
}

export function saveSelectedJourneyStage(
  journeyStage: JourneyStageName,
  opportunityId: string | null = null,
): StoredJourneyStageSelection {
  const selection: StoredJourneyStageSelection = { journeyStage, opportunityId };
  const storage = getSessionStorage();
  storage?.setItem(SELECTION_KEY, JSON.stringify(selection));
  return selection;
}

export function loadSelectedJourneyStage(): StoredJourneyStageSelection | null {
  const storage = getSessionStorage();
  if (!storage) {
    return null;
  }
  try {
    const raw = storage.getItem(SELECTION_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as StoredJourneyStageSelection;
    if (!isJourneyStageName(parsed.journeyStage)) {
      return null;
    }
    return {
      journeyStage: parsed.journeyStage,
      opportunityId:
        typeof parsed.opportunityId === "string" && parsed.opportunityId.trim()
          ? parsed.opportunityId
          : null,
    };
  } catch {
    return null;
  }
}

export function bindSelectedJourneyStage(opportunityId: string): StoredJourneyStageSelection | null {
  const current = loadSelectedJourneyStage();
  if (!current) {
    return null;
  }
  return saveSelectedJourneyStage(current.journeyStage, opportunityId);
}

export function journeyStageForGenerate(
  opportunityId?: string | null,
): JourneyStageName | undefined {
  const current = loadSelectedJourneyStage();
  if (!current) {
    return undefined;
  }
  if (current.opportunityId && opportunityId && current.opportunityId !== opportunityId) {
    return undefined;
  }
  return current.journeyStage;
}

export function clearSelectedJourneyStage(): void {
  getSessionStorage()?.removeItem(SELECTION_KEY);
}

export function continueHref(opportunityId: string | null): string {
  if (!opportunityId) {
    return "/upload?new=1";
  }
  return `/upload?opportunityId=${encodeURIComponent(opportunityId)}`;
}
