import { formatRecentDate } from "./recentPresentations";

export type ArchiveLifecycle = "filed" | "unavailable";

export interface ArchiveArtifact {
  id: string;
  opportunity_id: string;
  presentation_id: string;
  presentation_version_id: string;
  artifact_kind: string;
  content_type: string;
  file_name: string;
  size_bytes: number;
  sha256: string;
  status: string;
  client_name: string;
  opportunity_name: string;
  approved_by: string;
  approved_at: string;
  filed_at: string | null;
  journey_stage: string | null;
  download_url: string | null;
}

export interface ArchiveDownload {
  artifactId: string;
  path: string;
  fileName: string;
  kind: "pptx" | "pdf";
}

export interface ArchiveCard {
  key: string;
  opportunityId: string;
  presentationId: string;
  presentationVersionId: string;
  clientName: string;
  opportunityName: string;
  filedAt: string;
  lifecycle: ArchiveLifecycle;
  statusLabel: "Filed" | "Not available";
  journeyLabel?: string;
  openHref: string;
  pptx?: ArchiveDownload;
  pdf?: ArchiveDownload;
}

export interface ArchiveSearchQuery {
  search?: string;
  fromDate?: string;
  toDate?: string;
}

export const ARCHIVE_O2_NOTE =
  "These files are stored in Pitch Factory. An external archive is not connected yet.";

const JOURNEY_LABELS: Record<string, string> = {
  first_contact: "First contact",
  deepening: "Deepening",
  concretisation: "Concretisation",
};

export function journeyStageLabel(stage: string | null | undefined): string | undefined {
  if (!stage) {
    return undefined;
  }
  return JOURNEY_LABELS[stage];
}

export function hasActiveArchiveFilters(query: ArchiveSearchQuery): boolean {
  return Boolean(query.search?.trim() || query.fromDate || query.toDate);
}

export function buildArchiveListPath(query: ArchiveSearchQuery = {}): string {
  const params = new URLSearchParams();
  const search = query.search?.trim();
  if (search) {
    params.set("search", search);
  }
  if (query.fromDate) {
    params.set("from_date", query.fromDate);
  }
  if (query.toDate) {
    params.set("to_date", query.toDate);
  }
  const suffix = params.toString();
  return suffix ? `/archive/artifacts?${suffix}` : "/archive/artifacts";
}

function downloadFor(artifact: ArchiveArtifact): ArchiveDownload | undefined {
  if (artifact.status !== "filed" || !artifact.download_url) {
    return undefined;
  }
  if (artifact.artifact_kind !== "pptx" && artifact.artifact_kind !== "pdf") {
    return undefined;
  }
  return {
    artifactId: artifact.id,
    path: artifact.download_url,
    fileName: artifact.file_name,
    kind: artifact.artifact_kind,
  };
}

export function buildArchiveCards(
  artifacts: ArchiveArtifact[],
  currentUserId?: string,
): ArchiveCard[] {
  const cards = new Map<string, ArchiveCard>();
  for (const artifact of artifacts) {
    if (currentUserId && artifact.approved_by !== currentUserId) {
      continue;
    }
    const key = artifact.presentation_version_id || artifact.id;
    const existing = cards.get(key);
    const filedAt = artifact.filed_at || artifact.approved_at;
    const download = downloadFor(artifact);
    if (!existing) {
      const hasDownload = Boolean(download);
      cards.set(key, {
        key,
        opportunityId: artifact.opportunity_id,
        presentationId: artifact.presentation_id,
        presentationVersionId: artifact.presentation_version_id,
        clientName: artifact.client_name,
        opportunityName: artifact.opportunity_name,
        filedAt,
        lifecycle: hasDownload ? "filed" : "unavailable",
        statusLabel: hasDownload ? "Filed" : "Not available",
        journeyLabel: journeyStageLabel(artifact.journey_stage),
        openHref: `/deck-center?opportunityId=${encodeURIComponent(artifact.opportunity_id)}&presentationId=${encodeURIComponent(artifact.presentation_id)}&presentationVersionId=${encodeURIComponent(artifact.presentation_version_id)}`,
        pptx: download?.kind === "pptx" ? download : undefined,
        pdf: download?.kind === "pdf" ? download : undefined,
      });
      continue;
    }
    if (download?.kind === "pptx") {
      existing.pptx = download;
    }
    if (download?.kind === "pdf") {
      existing.pdf = download;
    }
    if (existing.pptx || existing.pdf) {
      existing.lifecycle = "filed";
      existing.statusLabel = "Filed";
    }
    if (Date.parse(filedAt) > Date.parse(existing.filedAt)) {
      existing.filedAt = filedAt;
    }
  }
  return [...cards.values()].sort(
    (left, right) => Date.parse(right.filedAt) - Date.parse(left.filedAt),
  );
}

export function formatArchiveDate(value: string): string {
  return formatRecentDate(value);
}

export function archiveEmptyCopy(hasFilters: boolean): {
  kicker: string;
  title: string;
  detail: string;
} {
  if (hasFilters) {
    return {
      kicker: "No matches",
      title: "No filed presentations match",
      detail: "Try a different client, opportunity name, or date range.",
    };
  }
  return {
    kicker: "Nothing filed yet",
    title: "Filed presentations will appear here",
    detail:
      "When a presentation is filed, you can find it by client, date, or opportunity name. Keep working from Recent presentations.",
  };
}
