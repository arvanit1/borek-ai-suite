import type { TranscriptQueueItem } from "@/lib/uploadQueue";

export interface OpportunityDraft {
  client_name: string;
  opportunity_name: string;
  department: string;
  language: string;
}

const ACTIVE_KEY = "borek.activeOpportunity";
const DRAFT_KEY = "borek.opportunityDraft";

export interface StoredOpportunity {
  id: string;
  client_name: string;
  opportunity_name: string;
  department: string;
  language: string;
}

interface CachedUploadSession {
  opportunity: StoredOpportunity | null;
  queue: TranscriptQueueItem[];
  summary: string | null;
}

let cachedUploadSession: CachedUploadSession = {
  opportunity: null,
  queue: [],
  summary: null,
};

function getSessionStorage(): Storage | null {
  try {
    const storage = globalThis.sessionStorage;
    if (!storage) {
      return null;
    }
    return storage;
  } catch {
    return null;
  }
}

export function opportunityLabel(
  opportunity: Pick<StoredOpportunity, "client_name" | "opportunity_name">,
): string {
  return `${opportunity.client_name} — ${opportunity.opportunity_name}`;
}

export function pipelineHref(path: string, opportunityId?: string | null): string {
  if (!opportunityId) {
    return path;
  }
  return `${path}?opportunityId=${encodeURIComponent(opportunityId)}`;
}

export function saveActiveOpportunity(opportunity: StoredOpportunity): void {
  cachedUploadSession = {
    ...cachedUploadSession,
    opportunity,
  };
  const storage = getSessionStorage();
  if (!storage) {
    return;
  }
  storage.setItem(ACTIVE_KEY, JSON.stringify(opportunity));
}

export function saveActiveOpportunityId(opportunityId: string): void {
  const current = loadActiveOpportunity();
  if (current?.id === opportunityId) {
    return;
  }
  saveActiveOpportunity({
    id: opportunityId,
    client_name: current?.client_name ?? "",
    opportunity_name: current?.opportunity_name ?? "",
    department: current?.department ?? "",
    language: current?.language ?? "en",
  });
}

export function loadActiveOpportunity(): StoredOpportunity | null {
  if (cachedUploadSession.opportunity?.id) {
    return cachedUploadSession.opportunity;
  }
  const storage = getSessionStorage();
  if (!storage) {
    return null;
  }
  try {
    const raw = storage.getItem(ACTIVE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as StoredOpportunity;
    if (parsed && typeof parsed.id === "string" && parsed.id.trim()) {
      cachedUploadSession = { ...cachedUploadSession, opportunity: parsed };
      return parsed;
    }
  } catch {
    return null;
  }
  return null;
}

export function saveOpportunityDraft(values: OpportunityDraft): void {
  const storage = getSessionStorage();
  if (!storage) {
    return;
  }
  storage.setItem(DRAFT_KEY, JSON.stringify(values));
}

export function loadOpportunityDraft(): OpportunityDraft | null {
  const storage = getSessionStorage();
  if (!storage) {
    return null;
  }
  try {
    const raw = storage.getItem(DRAFT_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as OpportunityDraft;
    if (!parsed || typeof parsed.client_name !== "string") {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearOpportunityDraft(): void {
  getSessionStorage()?.removeItem(DRAFT_KEY);
}

export function rememberUploadSession(session: CachedUploadSession): void {
  cachedUploadSession = session;
}

export function getCachedUploadSession(): CachedUploadSession {
  return cachedUploadSession;
}
