"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { useAuth } from "@/components/AuthProvider";
import { PipelineStepper } from "@/components/PipelineStepper";
import { SiteHeader } from "@/components/SiteHeader";
import { SlidePreviewCard } from "@/components/SlidePreviewCard";
import {
  downloadPresentationFile,
  generatePresentation,
  getDeckCenter,
  getLatestPresentation,
  waitForJob,
} from "@/lib/api";
import { isMissingPresentationError } from "@/lib/apiErrors";
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

  const loadPresentation = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const latest = await getLatestPresentation(accessToken, opportunityId);
      setPresentation(latest);
      await loadDeck(latest.id);
    } catch (loadError) {
      setPresentation(null);
      setDeck(null);
      if (!isMissingPresentationError(loadError)) {
        const message =
          loadError instanceof Error ? loadError.message : "Could not load presentation.";
        setError(message);
      }
    } finally {
      setBusy(false);
    }
  }, [accessToken, loadDeck, opportunityId]);

  useEffect(() => {
    if (!loading && accessToken) {
      void loadPresentation();
    }
  }, [accessToken, loading, loadPresentation]);

  async function handleGenerateDeck() {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const generated = await generatePresentation(accessToken, opportunityId);
      setInfo("Presentation rendering is running…");
      await waitForJob(accessToken, generated.job_id);
      setPresentation({
        id: generated.presentation_id,
        presentation_plan_id: generated.presentation_plan_id,
        name: "Presentation",
        status: "draft",
        created_at: new Date().toISOString(),
      });
      await loadDeck(generated.presentation_id);
      setInfo("Deck generated. Slide previews and downloads are ready below.");
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Deck generation failed.");
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
            {error ? <div className="alert alert-error">{error}</div> : null}
            {info ? <div className="upload-banner upload-banner-success">{info}</div> : null}

            {busy && !deck ? (
              <section className="upload-panel pipeline-panel-loading">
                <p className="upload-hint">Loading deck…</p>
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
