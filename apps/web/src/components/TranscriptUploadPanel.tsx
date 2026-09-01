"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { useAuth } from "@/components/AuthProvider";
import { FileUploadQueue } from "@/components/FileUploadQueue";
import { OpportunityForm } from "@/components/OpportunityForm";
import { PipelineStepper } from "@/components/PipelineStepper";
import { SiteHeader } from "@/components/SiteHeader";
import { UploadStepper } from "@/components/UploadStepper";
import {
  createOpportunity,
  getOpportunity,
  listTranscripts,
  uploadTranscript,
  type OpportunityResponse,
} from "@/lib/api";
import { isMissingOpportunityError } from "@/lib/apiErrors";
import {
  clearActiveOpportunity,
  clearOpportunityDraft,
  clearPipelineContext,
  getCachedUploadSession,
  opportunityLabel,
  pipelineHref,
  rememberUploadSession,
  saveActiveOpportunity,
  scopeUploadSession,
} from "@/lib/pipelineContext";
import { countByStatus } from "@/lib/uploadQueue";
import type { TranscriptQueueItem } from "@/lib/uploadQueue";
import { createRestoredQueueItem, updateQueueItem } from "@/lib/uploadQueue";

interface TranscriptUploadPanelProps {
  initialOpportunityId?: string | null;
  startFresh?: boolean;
}

function storedFromResponse(opportunity: OpportunityResponse) {
  return {
    id: opportunity.id,
    client_name: opportunity.client_name,
    opportunity_name: opportunity.opportunity_name,
    department: opportunity.department,
    language: opportunity.language,
  };
}

function mergeQueue(
  cached: TranscriptQueueItem[],
  remote: TranscriptQueueItem[],
): TranscriptQueueItem[] {
  const seenIds = new Set(
    cached.map((item) => item.transcriptId).filter((id): id is string => Boolean(id)),
  );
  const extras = remote.filter((item) => !item.transcriptId || !seenIds.has(item.transcriptId));
  return extras.length === 0 ? cached : [...cached, ...extras];
}

export function TranscriptUploadPanel({
  initialOpportunityId = null,
  startFresh = false,
}: TranscriptUploadPanelProps) {
  const router = useRouter();
  const { accessToken, isAuthenticated, loading, session } = useAuth();
  const cached = startFresh
    ? { opportunity: null, queue: [], summary: null }
    : scopeUploadSession(getCachedUploadSession(), initialOpportunityId);
  const [opportunity, setOpportunity] = useState<OpportunityResponse | null>(
    cached.opportunity && (!initialOpportunityId || cached.opportunity.id === initialOpportunityId)
      ? {
          ...cached.opportunity,
          status: "active",
        }
      : null,
  );
  const [opportunityId, setOpportunityId] = useState<string | null>(
    initialOpportunityId || cached.opportunity?.id || null,
  );
  const [opportunityLabelText, setOpportunityLabelText] = useState<string | null>(
    cached.opportunity ? opportunityLabel(cached.opportunity) : null,
  );
  const [queueItems, setQueueItems] = useState<TranscriptQueueItem[]>(cached.queue);
  const [uploadSummary, setUploadSummary] = useState<string | null>(cached.summary);

  const contextMatchesRequest = !initialOpportunityId || opportunityId === initialOpportunityId;
  const canUpload =
    isAuthenticated && !startFresh && Boolean(opportunityId) && contextMatchesRequest;
  const statusCounts = useMemo(() => countByStatus(queueItems), [queueItems]);

  useEffect(() => {
    if (!startFresh) {
      return;
    }
    clearPipelineContext();
    setOpportunity(null);
    setOpportunityId(null);
    setOpportunityLabelText(null);
    setQueueItems([]);
    setUploadSummary(null);
    router.replace("/upload");
  }, [router, startFresh]);

  useEffect(() => {
    if (!initialOpportunityId || opportunityId === initialOpportunityId) {
      return;
    }
    setOpportunity(null);
    setOpportunityId(initialOpportunityId);
    setOpportunityLabelText(null);
    setQueueItems([]);
    setUploadSummary(null);
  }, [initialOpportunityId, opportunityId]);

  useEffect(() => {
    rememberUploadSession({
      opportunity: opportunity ? storedFromResponse(opportunity) : getCachedUploadSession().opportunity,
      queue: queueItems,
      summary: uploadSummary,
    });
  }, [opportunity, queueItems, uploadSummary]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }
    if (startFresh) {
      return;
    }
    const token = accessToken;
    const cachedSession = scopeUploadSession(getCachedUploadSession(), initialOpportunityId);
    const restoreId = initialOpportunityId || cachedSession.opportunity?.id;
    if (!restoreId) {
      return;
    }
    const opportunityKey = restoreId;

    let cancelled = false;

    async function restore() {
      try {
        const loaded = await getOpportunity(token, opportunityKey);
        if (cancelled) {
          return;
        }
        const stored = storedFromResponse(loaded);
        setOpportunity(loaded);
        setOpportunityId(loaded.id);
        setOpportunityLabelText(opportunityLabel(stored));
        saveActiveOpportunity(stored);
        clearOpportunityDraft();
        if (typeof window !== "undefined") {
          window.history.replaceState(null, "", pipelineHref("/upload", loaded.id));
        }
      } catch (restoreError) {
        if (!cancelled && isMissingOpportunityError(restoreError)) {
          clearActiveOpportunity();
          setOpportunity(null);
          setOpportunityId(null);
          setOpportunityLabelText(null);
          setQueueItems([]);
          if (typeof window !== "undefined") {
            window.history.replaceState(null, "", "/upload");
          }
        }
        return;
      }

      try {
        const transcripts = await listTranscripts(token, opportunityKey);
        if (cancelled) {
          return;
        }
        const remoteItems = transcripts.map((item) =>
          createRestoredQueueItem(item.id, item.file_name),
        );
        setQueueItems((current) => {
          const merged = mergeQueue(current.length > 0 ? current : cachedSession.queue, remoteItems);
          return merged;
        });
        if (transcripts.length > 0) {
          setUploadSummary((current) =>
            current ??
              `${transcripts.length} transcript${transcripts.length === 1 ? "" : "s"} already ingested.`,
          );
        }
      } catch {
        // Keep the restored opportunity even if the transcript list cannot be loaded.
      }
    }

    void restore();
    return () => {
      cancelled = true;
    };
  }, [accessToken, initialOpportunityId, startFresh]);

  async function handleCreateOpportunity(values: {
    client_name: string;
    opportunity_name: string;
    department: string;
    language: string;
  }) {
    if (!accessToken) {
      throw new Error("Sign in is required before creating an opportunity.");
    }
    const created = await createOpportunity(accessToken, values);
    const stored = storedFromResponse(created);
    setOpportunity(created);
    setOpportunityId(created.id);
    setOpportunityLabelText(opportunityLabel(stored));
    setUploadSummary(null);
    saveActiveOpportunity(stored);
    clearOpportunityDraft();
    rememberUploadSession({
      opportunity: stored,
      queue: queueItems,
      summary: null,
    });
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", pipelineHref("/upload", created.id));
    }
  }

  async function handleUploadBatch(batch: TranscriptQueueItem[]) {
    if (!accessToken || !opportunityId || !contextMatchesRequest || startFresh) {
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
    <div className="app-workspace">
      <SiteHeader signedInEmail={session?.user.email} opportunityId={opportunityId} />

      <div className="app-shell app-workspace-body">
        {!loading && isAuthenticated ? <span data-testid="auth-ready" hidden /> : null}

        <PipelineStepper currentStep={1} opportunityId={opportunityId ?? undefined} />
        <AppPageHeader
          kicker="Step 1 of 4"
          title="Transcript ingestion"
          lead="Attach client discovery transcripts to an opportunity. Unsupported formats are filtered on your device before anything is sent to the server."
        />

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
                {opportunityLabelText ? <p className="upload-meta-title">{opportunityLabelText}</p> : null}
                <Link
                  href={pipelineHref("/framework-review", opportunityId)}
                  className="btn btn-primary btn-block"
                >
                  Review framework
                </Link>
              </div>
            ) : (
              <div className="upload-meta-card upload-meta-card-muted">
                <h3>Active opportunity</h3>
                <p className="upload-meta-empty">Create an opportunity to start this pipeline.</p>
              </div>
            )}
          </aside>

          <div className="upload-main">
            <section className="upload-panel">
              <header className="upload-panel-header">
                <div>
                  <h2>Opportunity details</h2>
                  <p>Every upload is scoped to a sales opportunity record.</p>
                </div>
              </header>
              <OpportunityForm
                disabled={!isAuthenticated || loading}
                existing={
                  opportunity
                    ? {
                        client_name: opportunity.client_name,
                        opportunity_name: opportunity.opportunity_name,
                        department: opportunity.department,
                        language: opportunity.language,
                      }
                    : null
                }
                onSubmit={handleCreateOpportunity}
              />
            </section>

            <section
              className={`upload-panel${
                statusCounts.success > 0 && statusCounts.pending === 0 ? " upload-panel-settled" : ""
              }`}
            >
              <header className="upload-panel-header">
                <div>
                  <h2>Transcript files</h2>
                  <p>
                    {uploadSummary
                      ? uploadSummary
                      : "Select or drop multiple files. Each file is validated and tracked individually."}
                  </p>
                </div>
                {queueItems.length > 0 && statusCounts.pending > 0 ? (
                  <div className="upload-stat-strip" aria-label="File queue summary">
                    {statusCounts.pending > 0 ? <span>{statusCounts.pending} ready</span> : null}
                    {statusCounts.rejected > 0 ? <span>{statusCounts.rejected} rejected</span> : null}
                    {statusCounts.success > 0 ? <span>{statusCounts.success} uploaded</span> : null}
                    {statusCounts.error > 0 ? <span>{statusCounts.error} failed</span> : null}
                  </div>
                ) : null}
              </header>

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
