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
    created_by: string;
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
  resourceLoadFailed?: boolean;
  activityAt?: string;
  job?: {
    job_type: string;
    status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
    current_stage: string;
    auto_continue?: boolean;
  };
}

export interface RecentJobCandidate {
  job_id: string;
  job_type: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  current_stage: string;
  started_at?: string | null;
  completed_at?: string | null;
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

export function selectRecentWorkJob(
  candidates: Array<RecentJobCandidate | null>,
): RecentJobCandidate | undefined {
  const relevant = candidates.filter(
    (job): job is RecentJobCandidate => Boolean(job && job.job_type !== "framework_render"),
  );
  const active = relevant.filter((job) => job.status === "QUEUED" || job.status === "RUNNING");
  const pool = active.length > 0 ? active : relevant;
  return pool.sort(
    (left, right) =>
      Date.parse(right.completed_at ?? right.started_at ?? "") -
      Date.parse(left.completed_at ?? left.started_at ?? ""),
  )[0];
}

function workflowJob(snapshot: RecentWorkSnapshot): RecentWorkSnapshot["job"] | undefined {
  return snapshot.job?.job_type === "framework_render" ? undefined : snapshot.job;
}

function lifecycleFor(snapshot: RecentWorkSnapshot): RecentLifecycle {
  const job = workflowJob(snapshot);
  if (job?.status === "FAILED") {
    return "needs_attention";
  }
  if (job?.status === "QUEUED" || job?.status === "RUNNING") {
    return job.job_type.toLowerCase().includes("framework")
      ? "analyzing"
      : "building_presentation";
  }
  if (snapshot.deck) {
    return "ready";
  }
  if (snapshot.resourceLoadFailed) {
    return "needs_attention";
  }
  if (job?.status === "COMPLETED") {
    const jobType = job.job_type.toLowerCase();
    if (jobType.includes("presentation_generation") || jobType.includes("slide")) {
      return "ready";
    }
    if (jobType.includes("plan") && job.auto_continue) {
      return "building_presentation";
    }
    return "needs_review";
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
  const job = workflowJob(snapshot);
  if (job && job.status !== "COMPLETED") {
    const jobType = job.job_type.toLowerCase();
    if (jobType.includes("framework")) {
      return opportunityHref("/framework-review", id);
    }
    if (jobType.includes("plan")) {
      return opportunityHref(
        job.auto_continue ? "/framework-review" : "/plan-preview",
        id,
      );
    }
    return opportunityHref("/deck-center", id);
  }
  if (job?.status === "COMPLETED") {
    const jobType = job.job_type.toLowerCase();
    if (jobType.includes("presentation_generation") || jobType.includes("slide")) {
      return opportunityHref("/deck-center", id);
    }
    if (jobType.includes("framework")) {
      return opportunityHref("/framework-review", id);
    }
    if (jobType.includes("plan")) {
      return opportunityHref(job.auto_continue ? "/framework-review" : "/plan-preview", id);
    }
  }
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

export function buildRecentWorkItems(
  snapshots: RecentWorkSnapshot[],
  currentUserId?: string,
): RecentWorkItem[] {
  return snapshots
    .filter(
      (snapshot) => !currentUserId || snapshot.opportunity.created_by === currentUserId,
    )
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
