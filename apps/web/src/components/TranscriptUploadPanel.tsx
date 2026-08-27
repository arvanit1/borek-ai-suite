"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { FileUploadQueue } from "@/components/FileUploadQueue";
import { OpportunityForm } from "@/components/OpportunityForm";
import { SiteHeader } from "@/components/SiteHeader";
import { UploadStepper } from "@/components/UploadStepper";
import { createOpportunity, uploadTranscript } from "@/lib/api";
import { countByStatus } from "@/lib/uploadQueue";
import type { TranscriptQueueItem } from "@/lib/uploadQueue";
import { updateQueueItem } from "@/lib/uploadQueue";

export function TranscriptUploadPanel() {
  const { accessToken, isAuthenticated, loading, session } = useAuth();
  const [opportunityId, setOpportunityId] = useState<string | null>(null);
  const [opportunityLabel, setOpportunityLabel] = useState<string | null>(null);
  const [queueItems, setQueueItems] = useState<TranscriptQueueItem[]>([]);
  const [uploadSummary, setUploadSummary] = useState<string | null>(null);

  const canUpload = isAuthenticated && Boolean(opportunityId);
  const statusCounts = useMemo(() => countByStatus(queueItems), [queueItems]);

  async function handleCreateOpportunity(values: {
    client_name: string;
    opportunity_name: string;
    department: string;
    language: string;
  }) {
    if (!accessToken) {
      throw new Error("Sign in is required before creating an opportunity.");
    }
    const opportunity = await createOpportunity(accessToken, values);
    setOpportunityId(opportunity.id);
    setOpportunityLabel(`${values.client_name} — ${values.opportunity_name}`);
    setUploadSummary(null);
  }

  async function handleUploadBatch(batch: TranscriptQueueItem[]) {
    if (!accessToken || !opportunityId) {
      throw new Error("Create an opportunity before uploading.");
    }

    let successCount = 0;
    let errorCount = 0;

    for (const item of batch) {
      setQueueItems((current) => updateQueueItem(current, item.id, { status: "uploading" }));

      try {
        const response = await uploadTranscript(accessToken, opportunityId, item.file);
        successCount += 1;
        setQueueItems((current) =>
          updateQueueItem(current, item.id, {
            status: "success",
            transcriptId: response.transcript.id,
            errorMessage: undefined,
          }),
        );
      } catch (uploadError) {
        errorCount += 1;
        const message =
          uploadError instanceof Error ? uploadError.message : "Upload failed.";
        setQueueItems((current) =>
          updateQueueItem(current, item.id, {
            status: "error",
            errorMessage: message,
          }),
        );
      }
    }

    if (errorCount === 0) {
      setUploadSummary(
        `${successCount} transcript${successCount === 1 ? "" : "s"} ingested successfully.`,
      );
    } else {
      setUploadSummary(
        `${successCount} uploaded, ${errorCount} failed — review the file list for details.`,
      );
    }
  }

  return (
    <div className="upload-page">
      <SiteHeader signedInEmail={session?.user.email} />

      <div className="upload-hero">
        <div className="app-shell upload-hero-inner">
          <h1>Transcript ingestion</h1>
          <p className="upload-lead">
            Attach client discovery transcripts to an opportunity. Unsupported formats are filtered
            on your device before anything is sent to the server.
          </p>
        </div>
      </div>

      <div className="app-shell upload-body">
        {!loading && isAuthenticated ? <span data-testid="auth-ready" hidden /> : null}

        <div className="upload-layout">
          <aside className="upload-sidebar">
            <UploadStepper
              opportunityReady={Boolean(opportunityId)}
              fileCount={queueItems.length}
              uploadedCount={statusCounts.success}
            />

            {opportunityId ? (
              <div className="upload-meta-card">
                <h3>Active opportunity</h3>
                {opportunityLabel ? <p className="upload-meta-title">{opportunityLabel}</p> : null}
                <code className="upload-meta-id">{opportunityId}</code>
                <Link
                  href={`/framework-review?opportunityId=${opportunityId}`}
                  className="btn btn-secondary btn-block"
                >
                  Review framework
                </Link>
              </div>
            ) : null}
          </aside>

          <div className="upload-main">
            <section className="upload-panel">
              <header className="upload-panel-header">
                <div>
                  <h2>1 · Opportunity details</h2>
                  <p>Every upload is scoped to a sales opportunity record.</p>
                </div>
              </header>
              <OpportunityForm
                disabled={!isAuthenticated || loading}
                onSubmit={handleCreateOpportunity}
              />
            </section>

            <section className="upload-panel">
              <header className="upload-panel-header">
                <div>
                  <h2>2 · Transcript files</h2>
                  <p>
                    Select or drop multiple files. Each file is validated and tracked individually.
                  </p>
                </div>
                {queueItems.length > 0 ? (
                  <div className="upload-stat-strip" aria-label="File queue summary">
                    <span>{statusCounts.pending} ready</span>
                    <span>{statusCounts.rejected} rejected</span>
                    <span>{statusCounts.success} uploaded</span>
                    {statusCounts.error > 0 ? <span>{statusCounts.error} failed</span> : null}
                  </div>
                ) : null}
              </header>

              {uploadSummary ? (
                <div className="upload-banner upload-banner-success">{uploadSummary}</div>
              ) : null}

              {!canUpload && isAuthenticated ? (
                <p className="upload-hint">
                  You may queue files now. Upload is enabled once an opportunity is created above.
                </p>
              ) : null}

              <FileUploadQueue
                items={queueItems}
                uploadDisabled={!canUpload || loading}
                onItemsChange={(items) => {
                  setQueueItems(items);
                  setUploadSummary(null);
                }}
                onUpload={handleUploadBatch}
              />
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
