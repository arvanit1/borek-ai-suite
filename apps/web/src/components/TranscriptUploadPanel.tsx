"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { useAuth } from "@/components/AuthProvider";
import { ClientLogoUpload } from "@/components/ClientLogoUpload";
import { FileUploadQueue } from "@/components/FileUploadQueue";
import { JourneyStageChoice, JourneyStageSelector } from "@/components/JourneyStageSelector";
import { OpportunityForm } from "@/components/OpportunityForm";
import { SiteHeader } from "@/components/SiteHeader";
import { WorkflowActionBar } from "@/components/WorkflowActionBar";
import {
  createOpportunity,
  getJourneyStageEligibility,
  getOpportunity,
  listTranscripts,
  updateOpportunity,
  uploadTranscript,
  type AdditionalClientInformation,
  type JourneyStageEligibilityResponse,
  type JourneyStageName,
  type OpportunityCreatePayload,
  type OpportunityResponse,
} from "@/lib/api";
import { isMissingOpportunityError, uploadErrorMessage } from "@/lib/apiErrors";
import {
  clearActiveOpportunity,
  clearOpportunityDraft,
  clearPipelineContext,
  getCachedUploadSession,
  pipelineHref,
  rememberUploadSession,
  saveActiveOpportunity,
  scopeUploadSession,
} from "@/lib/pipelineContext";
import {
  NEW_CLIENT_ELIGIBILITY,
  canSubmitJourneyStage,
  defaultStartableStage,
  eligibilityForOpportunity,
} from "@/lib/journeyStageEligibility";
import {
  bindSelectedJourneyStage,
  clearSelectedJourneyStage,
  journeyStageForGenerate,
  loadSelectedJourneyStage,
  saveSelectedJourneyStage,
} from "@/lib/journeyStageSelection";
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
    pii_redaction_enabled: opportunity.pii_redaction_enabled !== false,
    additional_client_information: opportunity.additional_client_information ?? null,
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

function initialJourneyStage(startFresh: boolean): JourneyStageName | null {
  const stored = loadSelectedJourneyStage();
  if (startFresh && stored?.opportunityId) {
    return defaultStartableStage(NEW_CLIENT_ELIGIBILITY);
  }
  return stored?.journeyStage ?? defaultStartableStage(NEW_CLIENT_ELIGIBILITY);
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
  const [queueItems, setQueueItems] = useState<TranscriptQueueItem[]>(cached.queue);
  const [uploadSummary, setUploadSummary] = useState<string | null>(cached.summary);
  const [eligibility, setEligibility] =
    useState<JourneyStageEligibilityResponse>(NEW_CLIENT_ELIGIBILITY);
  const [journeyStage, setJourneyStage] = useState<JourneyStageName | null>(() =>
    initialJourneyStage(startFresh),
  );
  const [eligibilityLoading, setEligibilityLoading] = useState(false);
  const [eligibilityError, setEligibilityError] = useState<string | null>(null);
  const [eligibilityReloadKey, setEligibilityReloadKey] = useState(0);

  const contextMatchesRequest = !initialOpportunityId || opportunityId === initialOpportunityId;
  const canUpload =
    isAuthenticated && !startFresh && Boolean(opportunityId) && contextMatchesRequest;
  const statusCounts = useMemo(() => countByStatus(queueItems), [queueItems]);

  useEffect(() => {
    if (!startFresh) {
      return;
    }
    clearPipelineContext();
    const storedSelection = loadSelectedJourneyStage();
    if (storedSelection?.opportunityId) {
      clearSelectedJourneyStage();
      const defaultStage = defaultStartableStage(NEW_CLIENT_ELIGIBILITY);
      setJourneyStage(defaultStage);
      if (defaultStage) {
        saveSelectedJourneyStage(defaultStage);
      }
    }
    setOpportunity(null);
    setOpportunityId(null);
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
    let cancelled = false;

    async function loadEligibility() {
      if (!accessToken || !opportunityId || startFresh) {
        setEligibility(NEW_CLIENT_ELIGIBILITY);
        setEligibilityError(null);
        setEligibilityLoading(false);
        const stored = loadSelectedJourneyStage()?.journeyStage;
        setJourneyStage(stored ?? defaultStartableStage(NEW_CLIENT_ELIGIBILITY));
        return;
      }
      setEligibilityLoading(true);
      setEligibilityError(null);
      try {
        const payload = eligibilityForOpportunity(
          await getJourneyStageEligibility(accessToken, opportunityId),
          opportunityId,
        );
        if (cancelled) {
          return;
        }
        setEligibility(payload);
        const stored = journeyStageForGenerate(opportunityId);
        setJourneyStage(
          stored && canSubmitJourneyStage(payload, stored)
            ? stored
            : defaultStartableStage(payload),
        );
      } catch {
        if (!cancelled) {
          setEligibilityError("Available outputs could not be loaded. Try again before changing the output.");
        }
      } finally {
        if (!cancelled) {
          setEligibilityLoading(false);
        }
      }
    }

    void loadEligibility();
    return () => {
      cancelled = true;
    };
  }, [accessToken, eligibilityReloadKey, opportunityId, startFresh]);

  function handleJourneyStageChange(stage: JourneyStageName) {
    setJourneyStage(stage);
    saveSelectedJourneyStage(stage, opportunityId);
  }

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
        saveActiveOpportunity(stored);
        clearOpportunityDraft();
        router.replace(pipelineHref("/upload", loaded.id));
      } catch (restoreError) {
        if (!cancelled && isMissingOpportunityError(restoreError)) {
          clearActiveOpportunity();
          setOpportunity(null);
          setOpportunityId(null);
          setQueueItems([]);
          router.replace("/upload");
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
  }, [accessToken, initialOpportunityId, router, startFresh]);

  async function handleCreateOpportunity(values: OpportunityCreatePayload) {
    if (!accessToken) {
      throw new Error("Sign in is required before creating an opportunity.");
    }
    const created = await createOpportunity(accessToken, values);
    const stored = storedFromResponse(created);
    setOpportunity(created);
    setOpportunityId(created.id);
    setUploadSummary(null);
    saveActiveOpportunity(stored);
    bindSelectedJourneyStage(created.id);
    if (journeyStage) {
      saveSelectedJourneyStage(journeyStage, created.id);
    }
    clearOpportunityDraft();
    rememberUploadSession({
      opportunity: stored,
      queue: queueItems,
      summary: null,
    });
    router.replace(pipelineHref("/upload", created.id));
  }

  async function handleUpdateClientInformation(
    additionalClientInformation: AdditionalClientInformation | null,
  ) {
    if (!accessToken || !opportunityId) {
      throw new Error("Create an opportunity before saving client information.");
    }
    const updated = await updateOpportunity(accessToken, opportunityId, {
      additional_client_information: additionalClientInformation,
    });
    const stored = storedFromResponse(updated);
    setOpportunity(updated);
    saveActiveOpportunity(stored);
    rememberUploadSession({
      opportunity: stored,
      queue: queueItems,
      summary: uploadSummary,
    });
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
        setQueueItems((current) =>
          updateQueueItem(current, item.id, {
            status: "error",
            errorMessage: uploadErrorMessage(uploadError),
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

        <WorkflowActionBar
          backHref="/"
          backLabel="Back to Recent"
          contextLabel="Current presentation"
          context={
            <>
              <strong>
                {opportunity
                  ? `${opportunity.client_name} - ${opportunity.opportunity_name}`
                  : "New presentation"}
              </strong>
              <JourneyStageChoice stage={journeyStage} />
            </>
          }
        >
          {opportunityId &&
          statusCounts.success > 0 &&
          statusCounts.pending === 0 &&
          statusCounts.uploading === 0 ? (
            <Link
              href={pipelineHref("/framework-review", opportunityId)}
              className="btn btn-primary"
            >
              Continue to customer story
            </Link>
          ) : (
            <button type="button" className="btn btn-primary" disabled>
              Continue to customer story
            </button>
          )}
        </WorkflowActionBar>

        <AppPageHeader
          kicker="Presentation intake"
          title="Create a presentation"
          lead="Confirm the client, add discovery transcripts, and continue to the customer story."
        />

        <div className="intake-main">
            <section className="journey-upload-summary" aria-labelledby="presentation-output-title">
              <div>
                <p className="journey-start-kicker">Presentation output</p>
                <h2 id="presentation-output-title">Selected for this presentation</h2>
                <JourneyStageChoice stage={journeyStage} />
              </div>
              <details className="journey-change-output">
                <summary>Change output</summary>
                {eligibilityError ? (
                  <div className="alert alert-error recent-error" role="alert">
                    <span>{eligibilityError}</span>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setEligibilityReloadKey((key) => key + 1)}
                    >
                      Try again
                    </button>
                  </div>
                ) : eligibilityLoading ? (
                  <p className="journey-start-loading">Loading available outputs...</p>
                ) : (
                  <JourneyStageSelector
                    eligibility={eligibility}
                    selected={journeyStage}
                    onSelect={handleJourneyStageChange}
                    disabled={!isAuthenticated || loading}
                  />
                )}
              </details>
            </section>

            <section className="upload-panel">
              <header className="upload-panel-header">
                <div>
                  <h2>Client and opportunity</h2>
                  <p>Create the workspace that will hold the transcripts and presentation.</p>
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
                        pii_redaction_enabled: opportunity.pii_redaction_enabled !== false,
                        additional_client_information: opportunity.additional_client_information ?? null,
                      }
                    : null
                }
                onSubmit={handleCreateOpportunity}
                onUpdateClientInformation={handleUpdateClientInformation}
                personalisationHint={
                  journeyStage === "first_contact"
                    ? "Save confirmed context for later. First contact stays generic and will not use client-specific references or branding."
                    : undefined
                }
                personalisation={
                  accessToken && opportunityId && journeyStage !== "first_contact" ? (
                    <ClientLogoUpload
                      accessToken={accessToken}
                      opportunityId={opportunityId}
                      clientName={opportunity?.client_name}
                    />
                  ) : journeyStage === "first_contact" ? (
                    <p className="client-information-stage-note">
                      Client branding becomes available for tailored presentations after First contact.
                    </p>
                  ) : null
                }
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
  );
}
