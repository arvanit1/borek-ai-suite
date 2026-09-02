"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { useAuth } from "@/components/AuthProvider";
import { PipelineStepper } from "@/components/PipelineStepper";
import { RecoveryBanner } from "@/components/RecoveryBanner";
import { SiteHeader } from "@/components/SiteHeader";
import { SlidePreviewCard } from "@/components/SlidePreviewCard";
import {
  ApiRequestError,
  downloadPresentationFile,
  generatePresentation,
  getActiveJob,
  getDeckCenter,
  getLatestPresentation,
  getPresentation,
  retryJob,
  waitForJob,
} from "@/lib/api";
import {
  isMissingPresentationError,
  isPresentationNotReadyError,
} from "@/lib/apiErrors";
import {
  generationProgressMessage,
  inspectActiveJob,
  stageGroupForPage,
} from "@/lib/jobReconnect";
import { buildDownloadFilename, mapDeckSlides } from "@/lib/deckCenter";
import type { DeckCenterResponse, PresentationResponse } from "@/lib/deckTypes";
import {
  jobFailureRecoveryNotice,
  recoveryActionHref,
  recoveryNoticeFromError,
  retryingRecoveryNotice,
  runningRecoveryNotice,
} from "@/lib/recoveryUx";
import type { RecoveryNotice } from "@/lib/recoveryUx";

interface DeckCenterPanelProps {
  opportunityId: string;
  presentationId?: string;
  presentationVersionId?: string;
}

export function DeckCenterPanel({
  opportunityId,
  presentationId: requestedPresentationId,
}: DeckCenterPanelProps) {
  const { accessToken, isAuthenticated, loading, session } = useAuth();
  const [presentation, setPresentation] = useState<PresentationResponse | null>(null);
  const [deck, setDeck] = useState<DeckCenterResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<RecoveryNotice | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [retryJobId, setRetryJobId] = useState<string | null>(null);
  const [recoveryTarget, setRecoveryTarget] = useState<"job" | "download-pptx" | "download-pdf">(
    "job",
  );

  const slideTiles = useMemo(() => (deck ? mapDeckSlides(deck) : []), [deck]);

  const loadDeck = useCallback(
    async (presentationId: string) => {
      if (!accessToken) {
        return;
      }
      const center = await getDeckCenter(accessToken, presentationId);
      setDeck(center);
    },
    [accessToken],
  );

  const applyLatestPresentation = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const latest = requestedPresentationId
        ? await getPresentation(accessToken, requestedPresentationId)
        : await getLatestPresentation(accessToken, opportunityId);
      setPresentation(latest);
      await loadDeck(latest.id);
    } catch (loadError) {
      setPresentation(null);
      setDeck(null);
      if (
        !isMissingPresentationError(loadError) &&
        !isPresentationNotReadyError(loadError)
      ) {
        throw loadError;
      }
    }
  }, [accessToken, loadDeck, opportunityId, requestedPresentationId]);

  const loadPresentation = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      await applyLatestPresentation();
    } catch (loadError) {
      setNotice(recoveryNoticeFromError(loadError, "deck"));
    } finally {
      setBusy(false);
    }
  }, [accessToken, applyLatestPresentation]);

  useEffect(() => {
    if (loading || !accessToken) {
      return;
    }
    const token = accessToken;
    let cancelled = false;
    async function bootstrap() {
      setBusy(true);
      setNotice(null);
      setInfo(null);
      setRetryJobId(null);
      try {
        const job = await getActiveJob(
          token,
          opportunityId,
          stageGroupForPage("deck"),
        );
        if (cancelled) {
          return;
        }
        const decision = inspectActiveJob(job, "deck");
        if (decision.action === "monitor") {
          setInfo(generationProgressMessage("deck", true));
          setNotice(runningRecoveryNotice("deck", decision.jobId));
          try {
            await waitForJob(token, decision.jobId);
            if (!cancelled) {
              setNotice(null);
            }
          } catch (monitorError) {
            if (!cancelled) {
              setInfo(null);
              setNotice(recoveryNoticeFromError(monitorError, "deck"));
              if (monitorError instanceof ApiRequestError && monitorError.retryable && monitorError.jobId) {
                setRetryJobId(monitorError.jobId);
              }
            }
          }
        } else if (decision.action === "failed") {
          setInfo(null);
          setNotice(jobFailureRecoveryNotice(decision.error, "deck", decision.jobId));
          if (decision.retryable) {
            setRetryJobId(decision.jobId);
          }
        }
        if (cancelled) {
          return;
        }
        try {
          await applyLatestPresentation();
        } catch (loadError) {
          if (!cancelled && decision.action !== "failed") {
            setNotice(recoveryNoticeFromError(loadError, "deck"));
          }
        }
      } catch (bootstrapError) {
        if (!cancelled) {
          setNotice(recoveryNoticeFromError(bootstrapError, "deck"));
        }
      } finally {
        if (!cancelled) {
          setBusy(false);
        }
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [accessToken, applyLatestPresentation, loading, opportunityId]);

  async function handleGenerateDeck() {
    if (!accessToken) {
      return;
    }
    setRecoveryTarget("job");
    setBusy(true);
    setNotice(null);
    setInfo(null);
    setRetryJobId(null);
    try {
      const generated = await generatePresentation(accessToken, opportunityId);
      setInfo(generationProgressMessage("deck", Boolean(generated.is_existing_job)));
      setNotice(runningRecoveryNotice("deck", generated.job_id));
      await waitForJob(accessToken, generated.job_id);
      setNotice(null);
      await applyLatestPresentation();
      setInfo("Deck generated. Slide previews and downloads are ready below.");
    } catch (generateError) {
      setInfo(null);
      setNotice(recoveryNoticeFromError(generateError, "deck"));
      if (generateError instanceof ApiRequestError && generateError.retryable && generateError.jobId) {
        setRetryJobId(generateError.jobId);
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleRetry() {
    if (!accessToken || !retryJobId) {
      return;
    }
    setRecoveryTarget("job");
    setBusy(true);
    setNotice(retryingRecoveryNotice("deck", retryJobId));
    setInfo("Retrying generation from the last failed stage…");
    try {
      const queued = await retryJob(accessToken, retryJobId);
      setRetryJobId(null);
      await waitForJob(accessToken, queued.job_id);
      setNotice(null);
      await applyLatestPresentation();
    } catch (retryError) {
      setInfo(null);
      setNotice(recoveryNoticeFromError(retryError, "deck"));
      if (retryError instanceof ApiRequestError && retryError.retryable && retryError.jobId) {
        setRetryJobId(retryError.jobId);
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleReconnect() {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setInfo(null);
    setNotice(runningRecoveryNotice("deck"));
    try {
      const job = await getActiveJob(accessToken, opportunityId, stageGroupForPage("deck"));
      const decision = inspectActiveJob(job, "deck");
      if (decision.action === "failed") {
        setRetryJobId(decision.retryable ? decision.jobId : null);
        setNotice(jobFailureRecoveryNotice(decision.error, "deck", decision.jobId));
        return;
      }
      if (decision.action === "monitor") {
        setNotice(runningRecoveryNotice("deck", decision.jobId));
        await waitForJob(accessToken, decision.jobId);
      }
      await applyLatestPresentation();
      setNotice(null);
    } catch (reconnectError) {
      setNotice(recoveryNoticeFromError(reconnectError, "deck"));
      if (
        reconnectError instanceof ApiRequestError &&
        reconnectError.retryable &&
        reconnectError.jobId
      ) {
        setRetryJobId(reconnectError.jobId);
      }
    } finally {
      setBusy(false);
    }
  }

  function handleRecoveryAction() {
    if (notice?.action?.kind === "RETRY") {
      void handleRetry();
      return;
    }
    if (
      notice?.action?.kind === "RECONNECT" ||
      notice?.action?.kind === "KEEP_CHECKING"
    ) {
      if (recoveryTarget === "download-pptx") {
        void handleDownload("pptx");
        return;
      }
      if (recoveryTarget === "download-pdf") {
        void handleDownload("pdf");
        return;
      }
      void handleReconnect();
    }
  }

  async function handleDownload(kind: "pptx" | "pdf") {
    if (!accessToken || !deck) {
      return;
    }
    setRecoveryTarget(kind === "pptx" ? "download-pptx" : "download-pdf");
    setBusy(true);
    setNotice(null);
    try {
      const path = kind === "pptx" ? deck.pptx_download_url : deck.pdf_download_url;
      const blob = await downloadPresentationFile(accessToken, path);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = buildDownloadFilename(deck.presentation_name, kind);
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      setNotice(
        recoveryNoticeFromError(downloadError, "deck", {
          connectionMessage: "The download was interrupted. Reconnect to try it again.",
        }),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-workspace">
      <SiteHeader signedInEmail={session?.user.email} opportunityId={opportunityId} />

      <div className="app-shell app-workspace-body">
        {!loading && isAuthenticated ? <span data-testid="auth-ready" hidden /> : null}

        {!loading && !isAuthenticated ? (
          <div className="upload-banner upload-banner-info">
            <div>
              <strong>Authentication required</strong>
              <p>Sign in to preview slides and download the presentation deck.</p>
            </div>
            <div className="upload-banner-actions">
              <Link href="/login" className="btn btn-primary">
                Sign in
              </Link>
            </div>
          </div>
        ) : null}

        <PipelineStepper
          currentStep={4}
          opportunityId={opportunityId}
          frameworkReady
          frameworkConfirmed
          planReady
        />
        <AppPageHeader
          kicker="Step 4 of 4"
          title="Deck center"
          lead="Preview rendered slide images and download the generated deck before sharing with clients."
        />

        <div className="upload-layout">
          <aside className="upload-sidebar">
            <div className="upload-meta-card">
              <h3>Active opportunity</h3>
              <p className="upload-meta-empty">Download the deck when slide previews look correct.</p>
              <Link
                href={`/plan-preview?opportunityId=${opportunityId}`}
                className="btn btn-secondary btn-block"
              >
                Back to plan
              </Link>
            </div>
          </aside>

          <div className="upload-main">
            {notice ? (
              <RecoveryBanner
                notice={
                  recoveryActionHref(notice, opportunityId)
                    ? {
                        ...notice,
                        action: {
                          ...notice.action!,
                          href: recoveryActionHref(notice, opportunityId),
                        },
                      }
                    : notice
                }
                busy={busy}
                onAction={handleRecoveryAction}
              />
            ) : null}
            {info && !notice ? <div className="upload-banner upload-banner-success">{info}</div> : null}

            {busy && !deck && !notice ? (
              <section className="upload-panel pipeline-panel-loading">
                <p className="upload-hint" data-testid="pipeline-job-progress">
                  {info ?? "Loading deck…"}
                </p>
              </section>
            ) : null}

            {!busy && !deck && isAuthenticated && !notice ? (
              <section className="upload-panel pipeline-empty-panel">
                <header className="upload-panel-header">
                  <div>
                    <h2>Generate the presentation deck</h2>
                    <p>
                      After the slide plan is approved, generate the full deck to render per-slide
                      PNG previews and enable `.pptx` / `.pdf` downloads.
                    </p>
                  </div>
                </header>
                <div className="pipeline-empty-body">
                  <p>No presentation deck exists yet for this opportunity.</p>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={busy}
                    onClick={() => void handleGenerateDeck()}
                  >
                    Generate deck
                  </button>
                </div>
              </section>
            ) : null}

            {deck && presentation && accessToken ? (
              <>
                <section className="upload-panel">
                  <header className="upload-panel-header">
                    <div>
                      <h2>{deck.presentation_name}</h2>
                      <p className="upload-hint">
                        Version {deck.version_number} · {slideTiles.length} slide
                        {slideTiles.length === 1 ? "" : "s"}
                      </p>
                    </div>
                    <div className="framework-toolbar-actions">
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={busy}
                        onClick={() => void handleDownload("pptx")}
                      >
                        Download .pptx
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={busy}
                        onClick={() => void handleDownload("pdf")}
                      >
                        Download .pdf
                      </button>
                    </div>
                  </header>
                </section>

                <section className="upload-panel">
                  <header className="upload-panel-header">
                    <div>
                      <h2>Slide previews</h2>
                      <p>Rendered preview image for each planned slide.</p>
                    </div>
                  </header>
                  <div className="deck-slide-grid" data-testid="deck-slide-grid">
                    {slideTiles.map((slide) => (
                      <SlidePreviewCard
                        key={`${slide.slideIndex}-${slide.layoutId}`}
                        accessToken={accessToken}
                        slideIndex={slide.slideIndex}
                        layoutId={slide.layoutId}
                        previewPath={slide.previewUrl}
                      />
                    ))}
                  </div>
                </section>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
