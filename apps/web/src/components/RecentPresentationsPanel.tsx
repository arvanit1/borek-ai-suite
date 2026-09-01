"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/components/AuthProvider";
import {
  downloadPresentationFile,
  getDeckCenter,
  getLatestFramework,
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
  type RecentWorkItem,
  type RecentWorkSnapshot,
} from "@/lib/recentPresentations";

async function optionalResource<T>(
  request: Promise<T>,
  isMissing: (error: unknown) => boolean,
): Promise<T | null> {
  try {
    return await request;
  } catch (error) {
    if (isMissing(error)) {
      return null;
    }
    throw error;
  }
}

async function loadSnapshot(
  accessToken: string,
  opportunity: ListedOpportunityResponse,
): Promise<RecentWorkSnapshot> {
  try {
    const [transcripts, framework, plan, presentation] = await Promise.all([
      listTranscripts(accessToken, opportunity.id),
      optionalResource(
        getLatestFramework(accessToken, opportunity.id),
        isMissingFrameworkError,
      ),
      optionalResource(
        getLatestPresentationPlan(accessToken, opportunity.id),
        isMissingPresentationPlanError,
      ),
      optionalResource(
        getLatestPresentation(accessToken, opportunity.id),
        isMissingPresentationError,
      ),
    ]);

    const deck = presentation
      ? await optionalResource(
          getDeckCenter(accessToken, presentation.id),
          isPresentationNotReadyError,
        )
      : null;

    return {
      opportunity,
      transcriptCount: transcripts.length,
      frameworkStatus: framework?.status,
      hasPlan: Boolean(plan),
      presentationId: presentation?.id,
      presentationName: deck?.presentation_name ?? presentation?.name,
      deck: deck ? { pptx_download_url: deck.pptx_download_url } : undefined,
    };
  } catch {
    return {
      opportunity,
      transcriptCount: 0,
      hasPlan: false,
      failed: true,
    };
  }
}

export function RecentPresentationsPanel() {
  const { accessToken, session } = useAuth();
  const [items, setItems] = useState<RecentWorkItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const loadRecent = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const opportunities = await listOpportunities(accessToken);
      const snapshots = await Promise.all(
        opportunities.map((opportunity) => loadSnapshot(accessToken, opportunity)),
      );
      setItems(buildRecentWorkItems(snapshots));
    } catch {
      setError("Recent presentations could not be loaded. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

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

        {!loading && items.length === 0 && !error ? (
          <section className="recent-empty">
            <p className="recent-empty-kicker">No presentations yet</p>
            <h2>Build your first customer presentation</h2>
            <p>Start with the opportunity details, then upload one or more discovery transcripts.</p>
            <Link href="/upload?new=1" className="btn btn-primary">
              Create presentation
            </Link>
          </section>
        ) : null}

        {!loading && items.length > 0 ? (
          <section className="recent-list" aria-label="Recent presentations">
            {items.map((item) => (
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
                  <Link href={item.actionHref} className="btn btn-primary">
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
