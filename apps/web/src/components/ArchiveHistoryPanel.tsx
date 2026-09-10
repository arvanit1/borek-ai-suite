"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { ArchiveHistoryView } from "@/components/ArchiveHistoryView";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/components/AuthProvider";
import { downloadPresentationFile, listArchiveArtifacts } from "@/lib/api";
import {
  buildArchiveCards,
  hasActiveArchiveFilters,
  type ArchiveCard,
  type ArchiveDownload,
  type ArchiveSearchQuery,
} from "@/lib/archiveHistory";

export function ArchiveHistoryPanel() {
  const { accessToken, session } = useAuth();
  const [items, setItems] = useState<ArchiveCard[]>([]);
  const [itemsAuthScope, setItemsAuthScope] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState<ArchiveSearchQuery>({});
  const [searchDraft, setSearchDraft] = useState("");
  const [fromDateDraft, setFromDateDraft] = useState("");
  const [toDateDraft, setToDateDraft] = useState("");
  const [downloadingKey, setDownloadingKey] = useState<string | null>(null);
  const loadRequestId = useRef(0);
  const currentUserId = session?.user.id;
  const authScope = currentUserId ?? accessToken;
  const visibleItems = authScope && itemsAuthScope === authScope ? items : [];

  const loadArchive = useCallback(
    async (nextQuery: ArchiveSearchQuery) => {
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
        const artifacts = await listArchiveArtifacts(accessToken, nextQuery);
        if (requestId === loadRequestId.current) {
          setItems(buildArchiveCards(artifacts, currentUserId));
          setItemsAuthScope(authScope);
        }
      } catch {
        if (requestId === loadRequestId.current) {
          setError("Filed presentations could not be loaded. Please try again.");
        }
      } finally {
        if (requestId === loadRequestId.current) {
          setLoading(false);
        }
      }
    },
    [accessToken, authScope, currentUserId],
  );

  useEffect(() => {
    void loadArchive(query);
  }, [loadArchive, query]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuery({
      search: searchDraft.trim() || undefined,
      fromDate: fromDateDraft || undefined,
      toDate: toDateDraft || undefined,
    });
  }

  function handleClear() {
    setSearchDraft("");
    setFromDateDraft("");
    setToDateDraft("");
    setQuery({});
  }

  async function handleDownload(item: ArchiveCard, download: ArchiveDownload) {
    if (!accessToken) {
      return;
    }
    const key = `${item.key}:${download.kind}`;
    setDownloadingKey(key);
    setError(null);
    try {
      const blob = await downloadPresentationFile(accessToken, download.path);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = download.fileName;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setError(
        download.kind === "pdf"
          ? "The PDF download is not available right now. Open the presentation to retry."
          : "The PowerPoint download is not available right now. Open the presentation to retry.",
      );
    } finally {
      setDownloadingKey(null);
    }
  }

  return (
    <div className="app-workspace recent-page">
      <SiteHeader signedInEmail={session?.user.email} />
      <main className="app-shell app-workspace-body">
        <ArchiveHistoryView
          items={visibleItems}
          loading={loading}
          error={error}
          query={query}
          searchDraft={searchDraft}
          fromDateDraft={fromDateDraft}
          toDateDraft={toDateDraft}
          hasActiveFilters={hasActiveArchiveFilters(query)}
          downloadingKey={downloadingKey}
          onSearchChange={setSearchDraft}
          onFromDateChange={setFromDateDraft}
          onToDateChange={setToDateDraft}
          onSubmit={handleSubmit}
          onClear={handleClear}
          onRetry={() => void loadArchive(query)}
          onDownload={(item, download) => void handleDownload(item, download)}
        />
      </main>
    </div>
  );
}
