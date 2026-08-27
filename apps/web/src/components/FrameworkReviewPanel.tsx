"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { FrameworkChapterView } from "@/components/FrameworkChapterView";
import { FrameworkRootFieldsPanel } from "@/components/FrameworkRootFieldsPanel";
import { PipelineStepper } from "@/components/PipelineStepper";
import { SiteHeader } from "@/components/SiteHeader";
import {
  confirmFramework,
  generateFramework,
  getLatestFramework,
  updateFramework as persistFramework,
} from "@/lib/api";
import { isMissingFrameworkError } from "@/lib/apiErrors";
import {
  EXPECTED_CHAPTER_COUNT,
  isFrameworkEditable,
  updateChapter,
  updateFrameworkRootField,
} from "@/lib/frameworkEdit";
import type { FrameworkObject, FrameworkVersionResponse } from "@/lib/frameworkTypes";

interface FrameworkReviewPanelProps {
  opportunityId: string;
}

export function FrameworkReviewPanel({ opportunityId }: FrameworkReviewPanelProps) {
  const { accessToken, isAuthenticated, loading, session } = useAuth();
  const [frameworkVersion, setFrameworkVersion] = useState<FrameworkVersionResponse | null>(null);
  const [frameworkJson, setFrameworkJson] = useState<FrameworkObject | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  const editable = frameworkVersion ? isFrameworkEditable(frameworkVersion.status) : false;
  const frameworkConfirmed = frameworkVersion?.status === "confirmed";

  const loadFramework = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const latest = await getLatestFramework(accessToken, opportunityId);
      setFrameworkVersion(latest);
      setFrameworkJson(latest.framework_json);
      setDirty(false);
    } catch (loadError) {
      setFrameworkVersion(null);
      setFrameworkJson(null);
      if (!isMissingFrameworkError(loadError)) {
        const message =
          loadError instanceof Error ? loadError.message : "Could not load framework.";
        setError(message);
      }
    } finally {
      setBusy(false);
    }
  }, [accessToken, opportunityId]);

  useEffect(() => {
    if (!loading && accessToken) {
      void loadFramework();
    }
  }, [accessToken, loading, loadFramework]);

  const chapterNav = useMemo(() => {
    if (!frameworkJson) {
      return [];
    }
    return frameworkJson.chapters.map((chapter, index) => ({
      index,
      chapterId: chapter.chapter_id,
      title: chapter.title,
      refCount: chapter.source_refs.length,
    }));
  }, [frameworkJson]);

  function applyFrameworkDraft(next: FrameworkObject) {
    setFrameworkJson(next);
    setDirty(true);
  }

  async function handleGenerate() {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await generateFramework(accessToken, opportunityId);
      setInfo("Framework generation queued. Loading the latest draft…");
      await loadFramework();
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Generate failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    if (!accessToken || !frameworkJson) {
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const saved = await persistFramework(accessToken, opportunityId, frameworkJson);
      setFrameworkVersion(saved);
      setFrameworkJson(saved.framework_json);
      setDirty(false);
      setInfo("Changes saved.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (dirty && frameworkJson) {
        await persistFramework(accessToken, opportunityId, frameworkJson);
      }
      const confirmed = await confirmFramework(accessToken, opportunityId);
      setFrameworkVersion(confirmed);
      setFrameworkJson(confirmed.framework_json);
      setDirty(false);
      setInfo("Framework confirmed. You can preview the presentation plan next.");
    } catch (confirmError) {
      setError(confirmError instanceof Error ? confirmError.message : "Confirm failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="upload-page">
      <SiteHeader signedInEmail={session?.user.email} />

      <div className="upload-hero">
        <div className="app-shell upload-hero-inner">
          <p className="upload-eyebrow">Pipeline · Step 2 of 4</p>
          <h1>Framework review</h1>
          <p className="upload-lead">
            Review all 14 chapters, inspect source references, and edit draft content before
            confirmation.
          </p>
        </div>
      </div>

      <div className="app-shell upload-body">
        {!loading && isAuthenticated ? <span data-testid="auth-ready" hidden /> : null}

        {!loading && !isAuthenticated ? (
          <div className="upload-banner upload-banner-info">
            <div>
              <strong>Authentication required</strong>
              <p>Sign in to review and edit the framework for this opportunity.</p>
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
              currentStep={2}
              frameworkReady={Boolean(frameworkVersion)}
              frameworkConfirmed={frameworkConfirmed}
            />

            <div className="upload-meta-card">
              <h3>Active opportunity</h3>
              <code className="upload-meta-id">{opportunityId}</code>
              <Link href={`/upload?opportunityId=${opportunityId}`} className="btn btn-secondary btn-block">
                Back to upload
              </Link>
              {frameworkConfirmed ? (
                <Link
                  href={`/plan-preview?opportunityId=${opportunityId}`}
                  className="btn btn-primary btn-block"
                >
                  Preview plan
                </Link>
              ) : null}
            </div>
          </aside>

          <div className="upload-main">
            {error ? <div className="alert alert-error">{error}</div> : null}
            {info ? <div className="upload-banner upload-banner-success">{info}</div> : null}

            {busy && !frameworkVersion ? (
              <section className="upload-panel pipeline-panel-loading">
                <p className="upload-hint">Loading framework…</p>
              </section>
            ) : null}

            {!busy && !frameworkVersion && isAuthenticated ? (
              <section className="upload-panel pipeline-empty-panel">
                <header className="upload-panel-header">
                  <div>
                    <h2>Generate the framework draft</h2>
                    <p>
                      After transcripts are uploaded, generate the 14-chapter Customer Framework
                      Report. You can review source references and edit every field before
                      confirming.
                    </p>
                  </div>
                </header>
                <div className="pipeline-empty-body">
                  <div className="pipeline-empty-icon" aria-hidden="true">
                    14
                  </div>
                  <p>No framework version exists yet for this opportunity.</p>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={busy}
                    onClick={() => void handleGenerate()}
                  >
                    Generate framework
                  </button>
                </div>
              </section>
            ) : null}

            {frameworkVersion && frameworkJson ? (
              <>
                <section className="upload-panel">
                  <header className="upload-panel-header">
                    <div>
                      <h2>Framework summary</h2>
                      <p>
                        Version {frameworkVersion.version_number} · status{" "}
                        <span className="framework-status-pill">{frameworkVersion.status}</span>
                      </p>
                    </div>
                    <div className="framework-toolbar-actions">
                      {editable ? (
                        <>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            disabled={busy || !dirty}
                            onClick={() => void handleSave()}
                          >
                            Save changes
                          </button>
                          <button
                            type="button"
                            className="btn btn-primary"
                            disabled={busy}
                            onClick={() => void handleConfirm()}
                          >
                            Confirm framework
                          </button>
                        </>
                      ) : null}
                    </div>
                  </header>

                  <div className="framework-meta-grid">
                    <div className="form-field">
                      <label htmlFor="framework-title">Framework title</label>
                      <input
                        id="framework-title"
                        value={frameworkJson.title}
                        disabled={!editable || busy}
                        onChange={(event) => {
                          applyFrameworkDraft(
                            updateFrameworkRootField(frameworkJson, "title", event.target.value),
                          );
                        }}
                      />
                    </div>
                    <div className="form-field">
                      <label htmlFor="framework-department">Department</label>
                      <input
                        id="framework-department"
                        value={frameworkJson.department}
                        disabled={!editable || busy}
                        onChange={(event) => {
                          applyFrameworkDraft(
                            updateFrameworkRootField(
                              frameworkJson,
                              "department",
                              event.target.value,
                            ),
                          );
                        }}
                      />
                    </div>
                    <div className="form-field">
                      <label>Chapters</label>
                      <div>
                        {frameworkJson.chapters.length} / {EXPECTED_CHAPTER_COUNT}
                      </div>
                    </div>
                  </div>
                </section>

                <FrameworkRootFieldsPanel
                  framework={frameworkJson}
                  editable={editable && !busy}
                  onChange={applyFrameworkDraft}
                />

                <div className="framework-layout">
                  <aside className="framework-sidebar">
                    <h2>Chapters</h2>
                    <ol className="framework-chapter-nav">
                      {chapterNav.map((item) => (
                        <li key={item.chapterId}>
                          <a
                            href={`#framework-chapter-${item.chapterId}`}
                            className="framework-chapter-nav-btn"
                          >
                            <span>{item.chapterId}</span>
                            <span>{item.title}</span>
                            {item.refCount > 0 ? (
                              <span className="framework-ref-count">{item.refCount} refs</span>
                            ) : null}
                          </a>
                        </li>
                      ))}
                    </ol>
                  </aside>

                  <div className="framework-main framework-all-chapters">
                    {frameworkJson.chapters.map((chapter, chapterIndex) => (
                      <div key={chapter.chapter_id} id={`framework-chapter-${chapter.chapter_id}`}>
                        <FrameworkChapterView
                          chapter={chapter}
                          editable={editable && !busy}
                          onChange={(nextChapter) => {
                            applyFrameworkDraft(
                              updateChapter(frameworkJson, chapterIndex, nextChapter),
                            );
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
