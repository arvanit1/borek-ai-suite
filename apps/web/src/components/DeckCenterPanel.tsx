"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { JobFailureAlert } from "@/components/JobFailureAlert";
import { PipelineStepper } from "@/components/PipelineStepper";
import { SiteHeader } from "@/components/SiteHeader";
import { SlidePreviewCard } from "@/components/SlidePreviewCard";
import {
  ApiRequestError,
  downloadPresentationFile,
  generatePresentation,
  getActiveJob,
  getDeckCenter,
  getLatestPresentation,
  retryJob,
  waitForJob,
} from "@/lib/api";
import { isMissingPresentationError } from "@/lib/apiErrors";
import {
  generationProgressMessage,
  inspectActiveJob,
  stageGroupForPage,
} from "@/lib/jobReconnect";
import { buildDownloadFilename, mapDeckSlides } from "@/lib/deckCenter";
import type { DeckCenterResponse, PresentationResponse } from "@/lib/deckTypes";

interface DeckCenterPanelProps {
  opportunityId: string;
}

export function DeckCenterPanel({ opportunityId }: DeckCenterPanelProps) {
  const { accessToken, isAuthenticated, loading, session } = useAuth();
  const [presentation, setPresentation] = useState<PresentationResponse | null>(null);
  const [deck, setDeck] = useState<DeckCenterResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [retryJobId, setRetryJobId] = useState<string | null>(null);

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
      const latest = await getLatestPresentation(accessToken, opportunityId);
      setPresentation(latest);
      await loadDeck(latest.id);
    } catch (loadError) {
      setPresentation(null);
      setDeck(null);
      if (!isMissingPresentationError(loadError)) {
        throw loadError;
      }
    }
  }, [accessToken, loadDeck, opportunityId]);

  const loadPresentation = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await applyLatestPresentation();
    } catch (loadError) {
      const message =
        loadError instanceof Error ? loadError.message : "Could not load presentation.";
      setError(message);
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
      setError(null);
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
          try {
            await waitForJob(token, decision.jobId);
          } catch (monitorError) {
            if (!cancelled) {
              setError(
                monitorError instanceof Error ? monitorError.message : "Generation job failed.",
              );
              if (monitorError instanceof ApiRequestError && monitorError.retryable && monitorError.jobId) {
                setRetryJobId(monitorError.jobId);
              }
            }
          }
        } else if (decision.action === "failed") {
          setError(decision.message);
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
            const message =
              loadError instanceof Error ? loadError.message : "Could not load presentation.";
            setError(message);
          }
        }
      } catch (bootstrapError) {
        if (!cancelled) {
          setError(
            bootstrapError instanceof Error
              ? bootstrapError.message
              : "Could not reconnect to the generation job.",
          );
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
    setBusy(true);
    setError(null);
    setInfo(null);
    setRetryJobId(null);
    try {
      const generated = await generatePresentation(accessToken, opportunityId);
      setInfo(generationProgressMessage("deck", Boolean(generated.is_existing_job)));
      await waitForJob(accessToken, generated.job_id);
      await applyLatestPresentation();
      setInfo("Deck generated. Slide previews and downloads are ready below.");
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Deck generation failed.");
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
    setBusy(true);
    setError(null);
    setInfo("Retrying generation from the last failed stage…");
    try {
      const queued = await retryJob(accessToken, retryJobId);
      setRetryJobId(null);
      await waitForJob(accessToken, queued.job_id);
      await applyLatestPresentation();
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "Retry failed.");
      if (retryError instanceof ApiRequestError && retryError.retryable && retryError.jobId) {
        setRetryJobId(retryError.jobId);
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleDownload(kind: "pptx" | "pdf") {
    if (!accessToken || !deck) {
      return;
    }
    setBusy(true);
    setError(null);
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
      setError(downloadError instanceof Error ? downloadError.message : "Download failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="upload-page">
      <SiteHeader signedInEmail={session?.user.email} />

      <div className="upload-hero">
        <div className="app-shell upload-hero-inner">

          <h1>Deck center</h1>
          <p className="upload-lead">
            Preview rendered slide images and download the generated deck before sharing with
            clients.
          </p>
        </div>
      </div>

      <div className="app-shell upload-body">
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

        <div className="upload-layout">
          <aside className="upload-sidebar">
            <PipelineStepper
              currentStep={4}
              frameworkReady
              frameworkConfirmed
              planReady
            />
            <div className="upload-meta-card">
              <h3>Active opportunity</h3>
              <code className="upload-meta-id">{opportunityId}</code>
              <Link
                href={`/plan-preview?opportunityId=${opportunityId}`}
                className="btn btn-secondary btn-block"
              >
                Back to plan
              </Link>
            </div>
          </aside>

          <div className="upload-main">
            {error ? (
              <JobFailureAlert
                message={error}
                retryable={Boolean(retryJobId)}
                retrying={busy}
                onRetry={() => void handleRetry()}
              />
            ) : null}
            {info ? <div className="upload-banner upload-banner-success">{info}</div> : null}

            {busy && !deck ? (
              <section className="upload-panel pipeline-panel-loading">
                <p className="upload-hint" data-testid="pipeline-job-progress">
                  {info ?? "Loading deck…"}
                </p>
              </section>
            ) : null}

            {!busy && !deck && isAuthenticated ? (
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
