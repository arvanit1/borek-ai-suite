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
  changePresentationSlideLayout,
  downloadPresentationFile,
  FRAMEWORK_JOB_TIMEOUT_MS,
  generatePresentation,
  getActiveJob,
  getDeckCenter,
  getJob,
  getLatestPresentation,
  getOpportunity,
  getPresentation,
  regeneratePresentationSlide,
  retryJob,
  waitForJob,
} from "@/lib/api";
import {
  isDeckFileMissingError,
  isMissingPresentationError,
  isPresentationNotReadyError,
} from "@/lib/apiErrors";
import { buildDownloadFilename, mapDeckSlides } from "@/lib/deckCenter";
import type { DeckCenterResponse, PresentationResponse } from "@/lib/deckTypes";
import {
  generationProgressMessage,
  inspectActiveJob,
  stageGroupForPage,
} from "@/lib/jobReconnect";
import { startPipelineParallelLoad } from "@/lib/pipelineParallelLoad";
import { opportunityLabel, pipelineHref } from "@/lib/pipelineContext";
import {
  ARTIFACTS_PARTIAL_LABEL,
  DOWNLOAD_PDF_LABEL,
  DOWNLOAD_POWERPOINT_LABEL,
  formatGeneratedAt,
  presentationReadyTitle,
  slideCountLabel,
  versionLabel,
} from "@/lib/presentationReady";
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
  const [opportunityName, setOpportunityName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [contentLoading, setContentLoading] = useState(true);
  const [jobPolling, setJobPolling] = useState(false);
  const [jobStage, setJobStage] = useState<string | null>(null);
  const [notice, setNotice] = useState<RecoveryNotice | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [retryJobId, setRetryJobId] = useState<string | null>(null);
  const [featuredSlideId, setFeaturedSlideId] = useState<string | null>(null);
  const [pptxAvailable, setPptxAvailable] = useState(true);
  const [pdfAvailable, setPdfAvailable] = useState(true);
  const [partialArtifacts, setPartialArtifacts] = useState(false);
  const [recoveryTarget, setRecoveryTarget] = useState<"job" | "download-pptx" | "download-pdf">(
    "job",
  );

  const slideTiles = useMemo(() => (deck ? mapDeckSlides(deck) : []), [deck]);
  const featuredSlide =
    slideTiles.find((slide) => slide.slideId === featuredSlideId) ?? slideTiles[0] ?? null;
  const ready = Boolean(deck && presentation);
  const generatedAt = formatGeneratedAt(presentation?.created_at);
  const version = versionLabel(deck?.version_number);

  const loadDeck = useCallback(
    async (presentationId: string) => {
      if (!accessToken) {
        return;
      }
      try {
        const center = await getDeckCenter(accessToken, presentationId);
        setDeck(center);
        setPartialArtifacts(center.slides.length === 0);
        setPptxAvailable(Boolean(center.pptx_download_url));
        setPdfAvailable(Boolean(center.pdf_download_url));
        const firstWithPreview = center.slides
          .slice()
          .sort((left, right) => left.slide_index - right.slide_index)
          .find((slide) => slide.preview_url);
        setFeaturedSlideId(firstWithPreview?.slide_id ?? center.slides[0]?.slide_id ?? null);
      } catch (loadError) {
        setDeck(null);
        if (isPresentationNotReadyError(loadError)) {
          setPartialArtifacts(true);
          return;
        }
        throw loadError;
      }
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
      if (isPresentationNotReadyError(loadError)) {
        setPartialArtifacts(true);
      }
    }
  }, [accessToken, loadDeck, opportunityId, requestedPresentationId]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }
    let cancelled = false;
    void getOpportunity(accessToken, opportunityId)
      .then((opportunity) => {
        if (!cancelled) {
          setOpportunityName(opportunityLabel(opportunity));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setOpportunityName(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, opportunityId]);

  useEffect(() => {
    if (loading || !accessToken) {
      return;
    }
    const token = accessToken;
    let cancelled = false;

    setContentLoading(true);
    setJobPolling(false);
    setJobStage(null);
    setNotice(null);
    setInfo(null);
    setRetryJobId(null);

    const cancel = startPipelineParallelLoad(
      "deck",
      {
        onContentLoaded: () => {},
        onContentMissing: () => {
          setPresentation(null);
          setDeck(null);
        },
        onContentLoadFinished: () => {
          setContentLoading(false);
        },
        onContentLoadError: (message) => {
          setNotice(recoveryNoticeFromError(new Error(message), "deck"));
        },
        onJobPollingStart: (message, stage, jobId) => {
          setJobPolling(true);
          setInfo(message);
          setJobStage(stage);
          setNotice(runningRecoveryNotice("deck", jobId));
        },
        onJobStageUpdate: (stage) => {
          setJobStage(stage);
        },
        onJobPollingFinished: () => {
          setJobPolling(false);
          setInfo(null);
          setJobStage(null);
          setNotice(null);
        },
        onJobFailed: (message, failedJobId) => {
          setNotice(
            recoveryNoticeFromError(
              {
                message,
                jobId: failedJobId ?? undefined,
                retryable: Boolean(failedJobId),
              },
              "deck",
            ),
          );
          setRetryJobId(failedJobId);
        },
      },
      {
        loadContent: async () => {
          if (cancelled) {
            return;
          }
          await applyLatestPresentation();
        },
        isMissingError: isMissingPresentationError,
        getActiveJob: () => getActiveJob(token, opportunityId, stageGroupForPage("deck")),
        getJob: (jobId) => getJob(token, jobId),
      },
    );

    return () => {
      cancelled = true;
      cancel();
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
      await waitForJob(accessToken, generated.job_id, FRAMEWORK_JOB_TIMEOUT_MS);
      setNotice(null);
      await applyLatestPresentation();
      setInfo(null);
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
      await waitForJob(accessToken, queued.job_id, FRAMEWORK_JOB_TIMEOUT_MS);
      setNotice(null);
      await applyLatestPresentation();
      setInfo(null);
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
        await waitForJob(accessToken, decision.jobId, FRAMEWORK_JOB_TIMEOUT_MS);
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
      if (isDeckFileMissingError(downloadError)) {
        if (kind === "pptx") {
          setPptxAvailable(false);
        } else {
          setPdfAvailable(false);
        }
        setPartialArtifacts(true);
      }
      setNotice(
        recoveryNoticeFromError(downloadError, "deck", {
          connectionMessage: "The download was interrupted. Reconnect to try it again.",
        }),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerateSlide(slideId: string) {
    if (!accessToken || !presentation) {
      return;
    }
    setRecoveryTarget("job");
    setBusy(true);
    setNotice(null);
    try {
      const queued = await regeneratePresentationSlide(accessToken, presentation.id, slideId);
      setInfo("Updating this slide…");
      setNotice(runningRecoveryNotice("deck", queued.job_id));
      await waitForJob(accessToken, queued.job_id, FRAMEWORK_JOB_TIMEOUT_MS);
      await loadDeck(presentation.id);
      setNotice(null);
      setInfo(null);
    } catch (regenerateError) {
      setInfo(null);
      setNotice(recoveryNoticeFromError(regenerateError, "deck"));
    } finally {
      setBusy(false);
    }
  }

  async function handleChangeLayout(slideId: string, layoutId: string) {
    if (!accessToken || !presentation) {
      return;
    }
    setRecoveryTarget("job");
    setBusy(true);
    setNotice(null);
    try {
      const queued = await changePresentationSlideLayout(
        accessToken,
        presentation.id,
        slideId,
        layoutId,
      );
      setInfo("Updating this slide layout…");
      setNotice(runningRecoveryNotice("deck", queued.job_id));
      await waitForJob(accessToken, queued.job_id, FRAMEWORK_JOB_TIMEOUT_MS);
      await loadDeck(presentation.id);
      setNotice(null);
      setInfo(null);
    } catch (layoutError) {
      setInfo(null);
      setNotice(recoveryNoticeFromError(layoutError, "deck"));
    } finally {
      setBusy(false);
    }
  }

  const metaParts = [
    opportunityName,
    deck ? slideCountLabel(slideTiles.length) : null,
    version,
    generatedAt ? `Generated ${generatedAt}` : null,
  ].filter(Boolean);

  return (
    <div className="app-workspace">
      <SiteHeader signedInEmail={session?.user.email} opportunityId={opportunityId} />

      <div className="app-shell app-workspace-body">
        {!loading && isAuthenticated ? <span data-testid="auth-ready" hidden /> : null}

        {!loading && !isAuthenticated ? (
          <div className="upload-banner upload-banner-info">
            <div>
              <strong>Authentication required</strong>
              <p>Sign in to preview and download this presentation.</p>
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
          presentationReady={ready}
        />
        <AppPageHeader
          kicker="Step 4 of 4"
          title={presentationReadyTitle(ready)}
          lead={
            ready
              ? "Preview the slides, then download the PowerPoint. A PDF copy is also available."
              : "When generation finishes, the preview and downloads appear here automatically."
          }
        />

        <div className="upload-layout">
          <aside className="upload-sidebar">
            <div className="upload-meta-card">
              <h3>Active opportunity</h3>
              <p className="upload-meta-empty">
                {opportunityName ?? "Download PowerPoint when the preview looks right."}
              </p>
              <Link
                href={pipelineHref("/plan-preview", opportunityId)}
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
            {info && !notice && !jobPolling ? (
              <div className="upload-banner upload-banner-success">{info}</div>
            ) : null}
            {partialArtifacts && ready ? (
              <div className="upload-banner upload-banner-info">{ARTIFACTS_PARTIAL_LABEL}</div>
            ) : null}

            {contentLoading && !presentation && !deck ? (
              <section className="upload-panel pipeline-panel-loading">
                <p className="upload-hint" data-testid="deck-loading">
                  Loading presentation…
                </p>
              </section>
            ) : null}

            {jobPolling ? (
              <section className="upload-panel pipeline-panel-loading">
                <p className="upload-hint" data-testid="pipeline-job-progress">
                  {info ?? "Presentation rendering is running…"}
                  {jobStage ? ` · ${jobStage.replaceAll("_", " ").toLowerCase()}` : ""}
                </p>
              </section>
            ) : null}

            {!contentLoading && !presentation && isAuthenticated && !notice ? (
              <section className="upload-panel pipeline-empty-panel">
                <header className="upload-panel-header">
                  <div>
                    <h2>Build the presentation</h2>
                    <p>
                      After the slide plan is ready, build the presentation. The preview loads
                      automatically when generation completes.
                    </p>
                  </div>
                </header>
                <div className="pipeline-empty-body">
                  <p>No presentation exists yet for this opportunity.</p>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={busy}
                    onClick={() => void handleGenerateDeck()}
                  >
                    Build presentation
                  </button>
                </div>
              </section>
            ) : null}

            {presentation && !deck && isAuthenticated && !contentLoading && !busy && !notice ? (
              <section className="upload-panel pipeline-empty-panel">
                <header className="upload-panel-header">
                  <div>
                    <h2>Preview isn’t ready yet</h2>
                    <p>
                      The presentation exists, but some files are still missing. You can wait for
                      generation to finish or try building again.
                    </p>
                  </div>
                </header>
                <div className="pipeline-empty-body">
                  {metaParts.length > 0 ? (
                    <p className="upload-hint">{metaParts.join(" · ")}</p>
                  ) : null}
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={busy}
                    onClick={() => void handleGenerateDeck()}
                  >
                    Build presentation
                  </button>
                </div>
              </section>
            ) : null}

            {deck && presentation && accessToken ? (
              <>
                <section className="upload-panel presentation-ready-panel" data-testid="presentation-ready">
                  <header className="upload-panel-header">
                    <div>
                      <h2>{deck.presentation_name}</h2>
                      <p className="upload-hint">{metaParts.join(" · ")}</p>
                    </div>
                    <div className="framework-toolbar-actions">
                      <button
                        type="button"
                        className="btn btn-primary"
                        data-testid="download-powerpoint"
                        disabled={busy || !pptxAvailable}
                        onClick={() => void handleDownload("pptx")}
                      >
                        {DOWNLOAD_POWERPOINT_LABEL}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        data-testid="download-pdf"
                        disabled={busy || !pdfAvailable}
                        onClick={() => void handleDownload("pdf")}
                      >
                        {DOWNLOAD_PDF_LABEL}
                      </button>
                    </div>
                  </header>
                  {!pptxAvailable ? (
                    <p className="upload-hint">PowerPoint isn’t available yet.</p>
                  ) : null}
                  {!pdfAvailable ? <p className="upload-hint">PDF isn’t available yet.</p> : null}

                  {featuredSlide ? (
                    <div className="presentation-hero" data-testid="presentation-hero-preview">
                      <SlidePreviewCard
                        accessToken={accessToken}
                        slideId={featuredSlide.slideId}
                        slideIndex={featuredSlide.slideIndex}
                        layoutId={featuredSlide.layoutId}
                        previewPath={featuredSlide.previewUrl}
                        featured
                        busy={busy}
                        canEdit
                        onRegenerate={(slideId) => void handleRegenerateSlide(slideId)}
                        onChangeLayout={(slideId, layoutId) => void handleChangeLayout(slideId, layoutId)}
                      />
                    </div>
                  ) : (
                    <p className="upload-hint">Slide previews aren’t available yet.</p>
                  )}

                  <details className="framework-details-disclosure">
                    <summary>Details</summary>
                    <dl className="presentation-diagnostics">
                      <div>
                        <dt>Presentation ID</dt>
                        <dd>{presentation.id}</dd>
                      </div>
                      <div>
                        <dt>Plan ID</dt>
                        <dd>{presentation.presentation_plan_id}</dd>
                      </div>
                      <div>
                        <dt>Status</dt>
                        <dd>{deck.status}</dd>
                      </div>
                      <div>
                        <dt>Slide layouts</dt>
                        <dd>
                          {slideTiles.length > 0
                            ? slideTiles
                                .map(
                                  (slide) =>
                                    `Slide ${slide.slideIndex + 1}: ${slide.layoutId}`,
                                )
                                .join(" · ")
                            : "None"}
                        </dd>
                      </div>
                    </dl>
                  </details>
                </section>

                <section className="upload-panel">
                  <header className="upload-panel-header">
                    <div>
                      <h2>Slide review</h2>
                      <p>Open a slide to preview it. You can regenerate a slide or change its layout when another layout in the same family is available.</p>
                    </div>
                  </header>
                  {slideTiles.length > 0 ? (
                    <div className="deck-slide-grid" data-testid="deck-slide-grid">
                      {slideTiles.map((slide) => (
                        <SlidePreviewCard
                          key={slide.slideId}
                          accessToken={accessToken}
                          slideId={slide.slideId}
                          slideIndex={slide.slideIndex}
                          layoutId={slide.layoutId}
                          previewPath={slide.previewUrl}
                          busy={busy}
                          canEdit
                          onSelect={() => setFeaturedSlideId(slide.slideId)}
                          onRegenerate={(slideId) => void handleRegenerateSlide(slideId)}
                          onChangeLayout={(slideId, layoutId) => void handleChangeLayout(slideId, layoutId)}
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="upload-hint">No slide previews were returned for this presentation.</p>
                  )}
                </section>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
