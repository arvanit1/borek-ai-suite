import Link from "next/link";
import React, { type FormEvent } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import {
  ARCHIVE_O2_NOTE,
  archiveEmptyCopy,
  formatArchiveDate,
  type ArchiveCard,
  type ArchiveDownload,
  type ArchiveSearchQuery,
} from "@/lib/archiveHistory";

export interface ArchiveHistoryViewProps {
  items: ArchiveCard[];
  loading: boolean;
  error: string | null;
  query: ArchiveSearchQuery;
  searchDraft: string;
  fromDateDraft: string;
  toDateDraft: string;
  hasActiveFilters: boolean;
  downloadingKey: string | null;
  onSearchChange: (value: string) => void;
  onFromDateChange: (value: string) => void;
  onToDateChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onClear: () => void;
  onRetry: () => void;
  onDownload: (item: ArchiveCard, download: ArchiveDownload) => void;
}

function downloadKey(item: ArchiveCard, kind: "pptx" | "pdf"): string {
  return `${item.key}:${kind}`;
}

export function ArchiveHistoryView({
  items,
  loading,
  error,
  query,
  searchDraft,
  fromDateDraft,
  toDateDraft,
  hasActiveFilters,
  downloadingKey,
  onSearchChange,
  onFromDateChange,
  onToDateChange,
  onSubmit,
  onClear,
  onRetry,
  onDownload,
}: ArchiveHistoryViewProps) {
  const empty = archiveEmptyCopy(hasActiveFilters);
  const showEmpty = !loading && items.length === 0 && !error;

  return (
    <div className="archive-page">
      <div className="recent-heading-row">
        <AppPageHeader
          kicker="Your workspace"
          title="Archive"
          lead="Find a previously filed presentation by client, date, or opportunity name."
        />
        <div className="archive-heading-actions">
          <Link href="/" className="btn btn-secondary">
            Recent presentations
          </Link>
          <Link href="/upload?new=1" className="btn btn-primary">
            Create presentation
          </Link>
        </div>
      </div>

      <p className="archive-o2-note">{ARCHIVE_O2_NOTE}</p>

      <form className="archive-filters" onSubmit={onSubmit} role="search">
        <div className="form-field">
          <label htmlFor="archive-search">Client or opportunity</label>
          <input
            id="archive-search"
            name="search"
            type="search"
            value={searchDraft}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search by client or opportunity name"
            autoComplete="off"
          />
        </div>
        <div className="form-field">
          <label htmlFor="archive-from-date">From date</label>
          <input
            id="archive-from-date"
            name="from_date"
            type="date"
            value={fromDateDraft}
            onChange={(event) => onFromDateChange(event.target.value)}
          />
        </div>
        <div className="form-field">
          <label htmlFor="archive-to-date">To date</label>
          <input
            id="archive-to-date"
            name="to_date"
            type="date"
            value={toDateDraft}
            onChange={(event) => onToDateChange(event.target.value)}
          />
        </div>
        <div className="archive-filter-actions">
          <button type="submit" className="btn btn-primary">
            Find
          </button>
          {hasActiveFilters ? (
            <button type="button" className="btn btn-secondary" onClick={onClear}>
              Clear
            </button>
          ) : null}
        </div>
      </form>

      {error ? (
        <div className="alert alert-error recent-error" role="alert">
          <span>{error}</span>
          <button type="button" className="btn btn-secondary" onClick={onRetry}>
            Try again
          </button>
        </div>
      ) : null}

      {loading ? (
        <section className="recent-state-card" aria-live="polite">
          <p>Loading your archive...</p>
        </section>
      ) : null}

      {showEmpty ? (
        <section className="recent-empty">
          <p className="recent-empty-kicker">{empty.kicker}</p>
          <h2>{empty.title}</h2>
          <p>{empty.detail}</p>
          {!hasActiveFilters ? (
            <Link href="/" className="btn btn-primary">
              Recent presentations
            </Link>
          ) : null}
        </section>
      ) : null}

      {!loading && items.length > 0 ? (
        <section className="recent-list" aria-label="Filed presentations">
          {items.map((item) => (
            <article className="recent-card" key={item.key}>
              <div className="recent-card-main">
                <div className="recent-card-copy">
                  <p className="recent-client">{item.clientName}</p>
                  <h2>{item.opportunityName}</h2>
                  <p className="recent-date">
                    Filed {formatArchiveDate(item.filedAt)}
                    {item.journeyLabel ? ` · ${item.journeyLabel}` : ""}
                  </p>
                </div>
                <span className={`recent-status recent-status-${item.lifecycle}`}>
                  {item.statusLabel}
                </span>
              </div>
              <div className="recent-card-actions">
                <Link href={item.openHref} className="btn btn-secondary">
                  Open
                </Link>
                {item.pptx ? (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={downloadingKey === downloadKey(item, "pptx")}
                    onClick={() => onDownload(item, item.pptx!)}
                  >
                    {downloadingKey === downloadKey(item, "pptx")
                      ? "Downloading..."
                      : "Download PowerPoint"}
                  </button>
                ) : null}
                {item.pdf ? (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={downloadingKey === downloadKey(item, "pdf")}
                    onClick={() => onDownload(item, item.pdf!)}
                  >
                    {downloadingKey === downloadKey(item, "pdf")
                      ? "Downloading..."
                      : "Download PDF"}
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </section>
      ) : null}

      {!loading && items.length > 0 && query.search ? (
        <p className="archive-result-hint">Showing filed presentations that match your search.</p>
      ) : null}
    </div>
  );
}
