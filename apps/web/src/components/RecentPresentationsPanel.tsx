"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { JourneyStartPanel } from "@/components/JourneyStartPanel";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/components/AuthProvider";
import { downloadPresentationFile, listRecentWork } from "@/lib/api";
import { buildDownloadFilename } from "@/lib/deckCenter";
import {
  buildRecentWorkItems,
  formatRecentDate,
  snapshotsFromRecentWorkApi,
  type RecentWorkItem,
} from "@/lib/recentPresentations";

export function RecentPresentationsPanel() {
  const { accessToken, session } = useAuth();
  const [items, setItems] = useState<RecentWorkItem[]>([]);
  const [itemsAuthScope, setItemsAuthScope] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [showJourneyStart, setShowJourneyStart] = useState(false);
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
      const snapshots = snapshotsFromRecentWorkApi(await listRecentWork(accessToken));
      if (requestId === loadRequestId.current) {
        setItems(buildRecentWorkItems(snapshots, currentUserId));
        setItemsAuthScope(authScope);
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

  useEffect(() => {
    if (window.location.hash === "#journey-start" || new URLSearchParams(window.location.search).has("new")) {
      setShowJourneyStart(true);
    }
  }, []);

  useEffect(() => {
    if (showJourneyStart) {
      document.getElementById("journey-start")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [showJourneyStart]);

  function openJourneyStart() {
    setShowJourneyStart(true);
    window.requestAnimationFrame(() => {
      document.getElementById("journey-start")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

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
      <SiteHeader
        signedInEmail={session?.user.email}
        onNewPresentation={openJourneyStart}
      />
      <main className="app-shell app-workspace-body">
        <div className="recent-heading-row">
          <AppPageHeader
            kicker="Your workspace"
            title="Recent presentations"
            lead="Continue active work or return to a completed customer presentation."
          />
          <div className="archive-heading-actions">
            <button
              type="button"
              className="btn btn-primary"
              aria-expanded={showJourneyStart}
              aria-controls="journey-start"
              onClick={() => setShowJourneyStart((visible) => !visible)}
            >
              {showJourneyStart ? "Close" : "New presentation"}
            </button>
          </div>
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
            <button type="button" className="btn btn-primary" onClick={openJourneyStart}>
              Choose an output
            </button>
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

        {showJourneyStart ? <JourneyStartPanel /> : null}
      </main>
    </div>
  );
}
