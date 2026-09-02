"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/components/AuthProvider";
import {
  downloadPresentationFile,
  getActiveJob,
  getDeckCenter,
  getJob,
  getLatestFramework,
  getLatestOpportunityJob,
  getLatestPresentation,
  getLatestPresentationPlan,
  listOpportunities,
  listTranscripts,
  type ListedOpportunityResponse,
} from "@/lib/api";
import {
  isMissingFrameworkError,
  isMissingPresentationError,
  isMissingPresentationPlanError,
  isPresentationNotReadyError,
} from "@/lib/apiErrors";
import { buildDownloadFilename } from "@/lib/deckCenter";
import {
  buildRecentWorkItems,
  formatRecentDate,
  latestActivityAt,
  selectRecentWorkJob,
  type RecentWorkItem,
  type RecentWorkSnapshot,
} from "@/lib/recentPresentations";

async function loadResource<T>(
  request: Promise<T>,
  fallback: T,
  isMissing?: (error: unknown) => boolean,
): Promise<{ value: T; failed: boolean }> {
  try {
    return { value: await request, failed: false };
  } catch (error) {
    if (isMissing?.(error)) {
      return { value: fallback, failed: false };
    }
    return { value: fallback, failed: true };
  }
}

async function loadSnapshot(
  accessToken: string,
  opportunity: ListedOpportunityResponse,
): Promise<RecentWorkSnapshot> {
  const [transcriptsResult, frameworkResult, planResult, presentationResult, latestJobResult,
    frameworkJobResult, presentationJobResult] = await Promise.all([
    loadResource(listTranscripts(accessToken, opportunity.id), []),
    loadResource(getLatestFramework(accessToken, opportunity.id), null, isMissingFrameworkError),
    loadResource(
      getLatestPresentationPlan(accessToken, opportunity.id),
      null,
      isMissingPresentationPlanError,
    ),
    loadResource(
      getLatestPresentation(accessToken, opportunity.id),
      null,
      isMissingPresentationError,
    ),
    loadResource(getLatestOpportunityJob(accessToken, opportunity.id), null),
    loadResource(getActiveJob(accessToken, opportunity.id, "framework"), null),
    loadResource(getActiveJob(accessToken, opportunity.id, "presentation"), null),
  ]);
  const transcripts = transcriptsResult.value;
  const framework = frameworkResult.value;
  const plan = planResult.value;
  const presentation = presentationResult.value;
  const latestJob = latestJobResult.value;
  const workflowJob = selectRecentWorkJob([
    frameworkJobResult.value,
    presentationJobResult.value,
    latestJob,
  ]);
  let resourceLoadFailed = [
    transcriptsResult,
    frameworkResult,
    planResult,
    presentationResult,
    latestJobResult,
    frameworkJobResult,
    presentationJobResult,
  ].some((result) => result.failed);
  let jobDetails = workflowJob?.job_id === latestJob?.job_id ? latestJob : null;
  if (workflowJob?.job_type === "presentation_planning" && !jobDetails) {
    const jobResult = await loadResource(getJob(accessToken, workflowJob.job_id), null);
    jobDetails = jobResult.value;
    resourceLoadFailed ||= jobResult.failed;
  }
  const enqueue = jobDetails?.result._enqueue;
  const autoContinue = Boolean(
    enqueue &&
      typeof enqueue === "object" &&
      (enqueue as Record<string, unknown>).auto_continue === true,
  );
  const deckResult = presentation
    ? await loadResource(
        getDeckCenter(accessToken, presentation.id),
        null,
        isPresentationNotReadyError,
      )
    : { value: null, failed: false };
  const deck = deckResult.value;
  resourceLoadFailed ||= deckResult.failed;

  return {
    opportunity,
    transcriptCount: transcripts.length,
    frameworkStatus: framework?.status,
    hasPlan: Boolean(plan),
    presentationId: presentation?.id,
    presentationName: deck?.presentation_name ?? presentation?.name,
    deck: deck ? { pptx_download_url: deck.pptx_download_url } : undefined,
    resourceLoadFailed,
    activityAt: latestActivityAt(
      opportunity.updated_at,
      opportunity.created_at,
      ...transcripts.map((transcript) => transcript.created_at),
      framework?.created_at,
      framework?.framework_json.updated_at,
      plan?.created_at,
      presentation?.created_at,
      latestJob?.completed_at,
      workflowJob?.started_at,
    ),
    job: workflowJob
      ? {
          job_type: workflowJob.job_type,
          status: workflowJob.status,
          current_stage: workflowJob.current_stage,
          auto_continue: autoContinue,
        }
      : undefined,
  };
}

export function RecentPresentationsPanel() {
  const { accessToken, session } = useAuth();
  const [items, setItems] = useState<RecentWorkItem[]>([]);
  const [itemsAuthScope, setItemsAuthScope] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const loadRequestId = useRef(0);
  const currentUserId = session?.user.id;
  const authScope = currentUserId ?? accessToken;
  const visibleItems = authScope && itemsAuthScope === authScope ? items : [];

  const loadRecent = useCallback(async () => {
    const requestId = ++loadRequestId.current;
    if (!accessToken || !authScope) {
      setItems([]);
      setItemsAuthScope(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const opportunities = await listOpportunities(accessToken);
      const snapshotResults = await Promise.allSettled(
        opportunities.map((opportunity) => loadSnapshot(accessToken, opportunity)),
      );
      if (requestId === loadRequestId.current) {
        const snapshots = snapshotResults.flatMap((result) =>
          result.status === "fulfilled" ? [result.value] : [],
        );
        setItems(buildRecentWorkItems(snapshots, currentUserId));
        setItemsAuthScope(authScope);
        if (snapshotResults.some((result) => result.status === "rejected")) {
          setError("Some recent presentations could not be loaded. Please try again.");
        }
      }
    } catch {
      if (requestId === loadRequestId.current) {
        setError("Recent presentations could not be loaded. Please try again.");
      }
    } finally {
      if (requestId === loadRequestId.current) {
        setLoading(false);
      }
    }
  }, [accessToken, authScope, currentUserId]);

  useEffect(() => {
    void loadRecent();
  }, [loadRecent]);

  async function handleDownload(item: RecentWorkItem) {
    if (!accessToken || !item.downloadPath) {
      return;
    }
    setDownloadingId(item.opportunityId);
    setError(null);
    try {
      const blob = await downloadPresentationFile(accessToken, item.downloadPath);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = buildDownloadFilename(
        item.presentationName ?? item.opportunityName,
        "pptx",
      );
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("The PowerPoint download is not available right now. Open the presentation to retry.");
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <div className="app-workspace recent-page">
      <SiteHeader signedInEmail={session?.user.email} />
      <main className="app-shell app-workspace-body">
        <div className="recent-heading-row">
          <AppPageHeader
            kicker="Your workspace"
            title="Recent presentations"
            lead="Continue active work or return to a completed customer presentation."
          />
          <Link href="/upload?new=1" className="btn btn-primary">
            Create presentation
          </Link>
        </div>

        {error ? (
          <div className="alert alert-error recent-error" role="alert">
            <span>{error}</span>
            <button type="button" className="btn btn-secondary" onClick={() => void loadRecent()}>
              Try again
            </button>
          </div>
        ) : null}

        {loading ? (
          <section className="recent-state-card" aria-live="polite">
            <p>Loading your recent work...</p>
          </section>
        ) : null}

        {!loading && visibleItems.length === 0 && !error ? (
          <section className="recent-empty">
            <p className="recent-empty-kicker">No presentations yet</p>
            <h2>Build your first customer presentation</h2>
            <p>Start with the opportunity details, then upload one or more discovery transcripts.</p>
            <Link href="/upload?new=1" className="btn btn-primary">
              Create presentation
            </Link>
          </section>
        ) : null}

        {!loading && visibleItems.length > 0 ? (
          <section className="recent-list" aria-label="Recent presentations">
            {visibleItems.map((item) => (
              <article className="recent-card" key={item.opportunityId}>
                <div className="recent-card-main">
                  <div className="recent-card-copy">
                    <p className="recent-client">{item.clientName}</p>
                    <h2>{item.opportunityName}</h2>
                    <p className="recent-date">Updated {formatRecentDate(item.updatedAt)}</p>
                  </div>
                  <span className={`recent-status recent-status-${item.lifecycle}`}>
                    {item.statusLabel}
                  </span>
                </div>
                <div className="recent-card-actions">
                  <Link href={item.actionHref} className="btn btn-secondary">
                    {item.actionLabel}
                  </Link>
                  {item.downloadPath ? (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      disabled={downloadingId === item.opportunityId}
                      onClick={() => void handleDownload(item)}
                    >
                      {downloadingId === item.opportunityId ? "Downloading..." : "Download PowerPoint"}
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </section>
        ) : null}
      </main>
    </div>
  );
}
