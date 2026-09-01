export type RecentLifecycle =
  | "draft"
  | "analyzing"
  | "needs_review"
  | "building_presentation"
  | "ready"
  | "needs_attention";

export interface RecentWorkSnapshot {
  opportunity: {
    id: string;
    client_name: string;
    opportunity_name: string;
    created_at: string;
    updated_at: string;
  };
  transcriptCount: number;
  frameworkStatus?: string;
  hasPlan: boolean;
  presentationId?: string;
  presentationName?: string;
  deck?: {
    pptx_download_url: string;
  };
  activityAt?: string;
  failed?: boolean;
}

export interface RecentWorkItem {
  opportunityId: string;
  clientName: string;
  opportunityName: string;
  updatedAt: string;
  lifecycle: RecentLifecycle;
  statusLabel: string;
  actionLabel: "Open" | "Resume";
  actionHref: string;
  presentationName?: string;
  downloadPath?: string;
}

const STATUS_LABELS: Record<RecentLifecycle, string> = {
  draft: "Draft",
  analyzing: "Analyzing",
  needs_review: "Needs review",
  building_presentation: "Building presentation",
  ready: "Ready",
  needs_attention: "Needs attention",
};

function opportunityHref(path: string, opportunityId: string): string {
  return `${path}?opportunityId=${encodeURIComponent(opportunityId)}`;
}

function lifecycleFor(snapshot: RecentWorkSnapshot): RecentLifecycle {
  if (snapshot.failed) {
    return "needs_attention";
  }
  if (snapshot.deck) {
    return "ready";
  }
  if (snapshot.presentationId) {
    return "building_presentation";
  }
  if (snapshot.hasPlan || snapshot.frameworkStatus) {
    return "needs_review";
  }
  if (snapshot.transcriptCount > 0) {
    return "analyzing";
  }
  return "draft";
}

function actionHrefFor(snapshot: RecentWorkSnapshot, lifecycle: RecentLifecycle): string {
  const id = snapshot.opportunity.id;
  if (lifecycle === "ready" || snapshot.presentationId) {
    return opportunityHref("/deck-center", id);
  }
  if (snapshot.hasPlan || snapshot.frameworkStatus === "confirmed") {
    return opportunityHref("/plan-preview", id);
  }
  if (snapshot.frameworkStatus || snapshot.transcriptCount > 0) {
    return opportunityHref("/framework-review", id);
  }
  return opportunityHref("/upload", id);
}

export function buildRecentWorkItems(snapshots: RecentWorkSnapshot[]): RecentWorkItem[] {
  return snapshots
    .map((snapshot) => {
      const lifecycle = lifecycleFor(snapshot);
      return {
        opportunityId: snapshot.opportunity.id,
        clientName: snapshot.opportunity.client_name,
        opportunityName: snapshot.opportunity.opportunity_name,
        updatedAt:
          snapshot.activityAt || snapshot.opportunity.updated_at || snapshot.opportunity.created_at,
        lifecycle,
        statusLabel: STATUS_LABELS[lifecycle],
        actionLabel:
          lifecycle === "draft" || lifecycle === "ready" || lifecycle === "needs_attention"
            ? "Open"
            : "Resume",
        actionHref: actionHrefFor(snapshot, lifecycle),
        presentationName: snapshot.presentationName,
        downloadPath: lifecycle === "ready" ? snapshot.deck?.pptx_download_url : undefined,
      } satisfies RecentWorkItem;
    })
    .sort((left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt));
}

export function latestActivityAt(...values: Array<string | null | undefined>): string {
  const valid = values
    .filter(
      (value): value is string =>
        typeof value === "string" && !Number.isNaN(Date.parse(value)),
    )
    .sort((left, right) => Date.parse(right) - Date.parse(left));
  return valid[0] ?? "";
}

export function formatRecentDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Date unavailable";
  }
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${date.getUTCDate()} ${months[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
}
