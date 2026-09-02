"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { useAuth } from "@/components/AuthProvider";
import { FrameworkChapterView } from "@/components/FrameworkChapterView";
import { FrameworkReviewSummary } from "@/components/FrameworkReviewSummary";
import { FrameworkRootFieldsPanel } from "@/components/FrameworkRootFieldsPanel";
import { JobFailureAlert } from "@/components/JobFailureAlert";
import { PipelineStepper } from "@/components/PipelineStepper";
import { SiteHeader } from "@/components/SiteHeader";
import {
  ApiRequestError,
  FRAMEWORK_JOB_TIMEOUT_MS,
  confirmFramework,
  downloadFrameworkRender,
  generateFramework,
  generatePresentationPlan,
  getActiveJob,
  getFrameworkReview,
  getLatestFramework,
  listTranscripts,
  regenerateFrameworkChapter,
  retryJob,
  updateFramework as persistFramework,
  waitForJob,
} from "@/lib/api";
import {
  buildFrameworkDownloadFilename,
  buildFrameworkRenderPath,
} from "@/lib/frameworkExport";
import { isMissingFrameworkError } from "@/lib/apiErrors";
import {
  generationProgressMessage,
  inspectActiveJob,
  stageGroupForPage,
} from "@/lib/jobReconnect";
import { countFactSourceRefs } from "@/lib/frameworkEvidence";
import {
  EXPECTED_CHAPTER_COUNT,
  canEditFramework,
  isFrameworkConfirmed,
  updateChapter,
  updateFrameworkRootField,
} from "@/lib/frameworkEdit";
import { customerStatusLabel } from "@/lib/frameworkLabels";
import {
  canApproveAndBuild,
  isApprovalBlocked,
  reviewPayloadFromUnknown,
  type FrameworkReviewPayload,
} from "@/lib/frameworkReview";
import { pipelineHref } from "@/lib/pipelineContext";
import type { FrameworkObject, FrameworkVersionResponse } from "@/lib/frameworkTypes";

interface FrameworkReviewPanelProps {
  opportunityId: string;
}

export function FrameworkReviewPanel({ opportunityId }: FrameworkReviewPanelProps) {
  const router = useRouter();
  const { accessToken, isAuthenticated, loading, session } = useAuth();
  const [frameworkVersion, setFrameworkVersion] = useState<FrameworkVersionResponse | null>(null);
  const [frameworkJson, setFrameworkJson] = useState<FrameworkObject | null>(null);
  const [review, setReview] = useState<FrameworkReviewPayload | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [humanConfirmed, setHumanConfirmed] = useState(false);
  const [regeneratingChapterId, setRegeneratingChapterId] = useState<string | null>(null);
  const [retryJobId, setRetryJobId] = useState<string | null>(null);
  const [transcriptCount, setTranscriptCount] = useState<number | null>(null);
  const [activeChapterId, setActiveChapterId] = useState<string | null>(null);
  const [hoveredChapterId, setHoveredChapterId] = useState<string | null>(null);
  const [downloadingFormat, setDownloadingFormat] = useState<"docx" | "pdf" | null>(null);
  const chapterNavItemRefs = useRef<Record<string, HTMLAnchorElement | null>>({});

  const editable = frameworkVersion
    ? canEditFramework(frameworkVersion.status, frameworkJson?.status)
    : false;
  const frameworkConfirmed = Boolean(
    frameworkVersion &&
      (isFrameworkConfirmed(frameworkVersion.status) ||
        (frameworkJson != null && isFrameworkConfirmed(frameworkJson.status))),
  );

  const applyReview = useCallback(
    async (source?: unknown) => {
      const extracted = reviewPayloadFromUnknown(source);
      if (extracted) {
        setReview(extracted);
      }
      if (!accessToken) {
        return extracted ?? null;
      }
      try {
        const payload = await getFrameworkReview(accessToken, opportunityId);
        setReview(payload);
        return payload;
      } catch {
        if (!extracted) {
          setReview(null);
        }
        return extracted ?? null;
      }
    },
    [accessToken, opportunityId],
  );

  const applyLatestFramework = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const latest = await getLatestFramework(accessToken, opportunityId);
      setFrameworkVersion(latest);
      setFrameworkJson(latest.framework_json);
      setDirty(false);
      setHumanConfirmed(false);
      await applyReview(latest);
    } catch (loadError) {
      setFrameworkVersion(null);
      setFrameworkJson(null);
      setReview(null);
      if (!isMissingFrameworkError(loadError)) {
        throw loadError;
      }
    }
  }, [accessToken, applyReview, opportunityId]);

  const loadFramework = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await applyLatestFramework();
    } catch (loadError) {
      const message =
        loadError instanceof Error ? loadError.message : "Could not load framework.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }, [accessToken, applyLatestFramework]);

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
          stageGroupForPage("framework"),
        );
        if (cancelled) {
          return;
        }
        const decision = inspectActiveJob(job, "framework");
        if (decision.action === "monitor") {
          setInfo(generationProgressMessage("framework", true));
          try {
            await waitForJob(token, decision.jobId, FRAMEWORK_JOB_TIMEOUT_MS);
          } catch (monitorError) {
            if (!cancelled) {
              setInfo(null);
              setError(
                monitorError instanceof Error ? monitorError.message : "Generation job failed.",
              );
              if (monitorError instanceof ApiRequestError && monitorError.retryable && monitorError.jobId) {
                setRetryJobId(monitorError.jobId);
              }
            }
          }
        } else if (decision.action === "failed") {
          setInfo(null);
          setError(decision.message);
          if (decision.retryable) {
            setRetryJobId(decision.jobId);
          }
        }
        if (cancelled) {
          return;
        }
        try {
          await applyLatestFramework();
        } catch (loadError) {
          if (!cancelled && decision.action !== "failed") {
            const message =
              loadError instanceof Error ? loadError.message : "Could not load framework.";
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
  }, [accessToken, applyLatestFramework, loading, opportunityId]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }
    let cancelled = false;
    void listTranscripts(accessToken, opportunityId)
      .then((rows) => {
        if (!cancelled) {
          setTranscriptCount(rows.length);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTranscriptCount(0);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, opportunityId]);

  const chapterNav = useMemo(() => {
    if (!frameworkJson) {
      return [];
    }
    return frameworkJson.chapters.map((chapter, index) => ({
      index,
      chapterId: chapter.chapter_id,
      title: chapter.title,
      refCount: countFactSourceRefs(chapter),
    }));
  }, [frameworkJson]);

  const chapterIdsKey = chapterNav.map((item) => item.chapterId).join("|");
  const highlightedChapterId = hoveredChapterId ?? activeChapterId;

  useEffect(() => {
    if (!chapterIdsKey) {
      setActiveChapterId(null);
      return;
    }

    const ids = chapterIdsKey.split("|");
    const headerOffset = 140;

    function updateActiveChapter() {
      let current = ids[0];
      for (const id of ids) {
        const node = document.getElementById(`framework-chapter-${id}`);
        if (!node) {
          continue;
        }
        if (node.getBoundingClientRect().top - headerOffset <= 0) {
          current = id;
        }
      }
      setActiveChapterId((previous) => (previous === current ? previous : current));
    }

    updateActiveChapter();
    window.addEventListener("scroll", updateActiveChapter, { passive: true });
    window.addEventListener("resize", updateActiveChapter);
    return () => {
      window.removeEventListener("scroll", updateActiveChapter);
      window.removeEventListener("resize", updateActiveChapter);
    };
  }, [chapterIdsKey]);

  useEffect(() => {
    if (!highlightedChapterId) {
      return;
    }
    const item = chapterNavItemRefs.current[highlightedChapterId];
    const sidebar = item?.closest(".framework-sidebar");
    if (!item || !(sidebar instanceof HTMLElement)) {
      return;
    }
    const sidebarRect = sidebar.getBoundingClientRect();
    const itemRect = item.getBoundingClientRect();
    const padding = 8;
    if (itemRect.top < sidebarRect.top + padding) {
      sidebar.scrollTop -= sidebarRect.top + padding - itemRect.top;
    } else if (itemRect.bottom > sidebarRect.bottom - padding) {
      sidebar.scrollTop += itemRect.bottom - (sidebarRect.bottom - padding);
    }
  }, [highlightedChapterId]);

  function applyFrameworkDraft(next: FrameworkObject) {
    setFrameworkJson(next);
    setDirty(true);
  }

  function jumpToChapter(chapterId: string) {
    setActiveChapterId(chapterId);
    const node = document.getElementById(`framework-chapter-${chapterId}`);
    node?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function handleGenerate() {
    if (!accessToken) {
      return;
    }
    if ((transcriptCount ?? 0) === 0) {
      setError("Upload at least one transcript before generating a framework.");
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    setRetryJobId(null);
    try {
      const generated = await generateFramework(accessToken, opportunityId);
      setInfo(generationProgressMessage("framework", Boolean(generated.is_existing_job)));
      await waitForJob(accessToken, generated.job_id, FRAMEWORK_JOB_TIMEOUT_MS);
      await loadFramework();
    } catch (generateError) {
      setInfo(null);
      setError(generateError instanceof Error ? generateError.message : "Generate failed.");
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
      await waitForJob(accessToken, queued.job_id, FRAMEWORK_JOB_TIMEOUT_MS);
      await loadFramework();
    } catch (retryError) {
      setInfo(null);
      setError(retryError instanceof Error ? retryError.message : "Retry failed.");
      if (retryError instanceof ApiRequestError && retryError.retryable && retryError.jobId) {
        setRetryJobId(retryError.jobId);
      }
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
      await applyReview(saved);
      setInfo("Changes saved.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDownloadFramework(format: "docx" | "pdf") {
    if (!accessToken || !frameworkVersion || !frameworkJson) {
      return;
    }
    setDownloadingFormat(format);
    setError(null);
    try {
      const path = buildFrameworkRenderPath(frameworkVersion.id, format);
      const blob = await downloadFrameworkRender(accessToken, path);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = buildFrameworkDownloadFilename(frameworkJson.title, format);
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError(
        downloadError instanceof Error ? downloadError.message : "Framework download failed.",
      );
    } finally {
      setDownloadingFormat(null);
    }
  }

  async function handleRegenerateChapter(chapterId: string) {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setRegeneratingChapterId(chapterId);
    setError(null);
    setInfo(null);
    try {
      if (dirty && frameworkJson) {
        await persistFramework(accessToken, opportunityId, frameworkJson);
      }
      const queued = await regenerateFrameworkChapter(accessToken, opportunityId, chapterId);
      setInfo(`Updating chapter ${chapterId}…`);
      await waitForJob(accessToken, queued.job_id, FRAMEWORK_JOB_TIMEOUT_MS);
      await loadFramework();
      setInfo(`Chapter ${chapterId} was updated. Other chapters were left unchanged.`);
    } catch (regenerateError) {
      setError(
        regenerateError instanceof Error ? regenerateError.message : "Chapter regenerate failed.",
      );
    } finally {
      setRegeneratingChapterId(null);
      setBusy(false);
    }
  }

  async function handleApprove() {
    if (!accessToken) {
      return;
    }
    const blocked = review ? isApprovalBlocked(review) : false;
    if (
      !canApproveAndBuild({
        editable,
        confirmed: frameworkConfirmed,
        humanConfirmed,
        blocked,
      })
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (dirty && frameworkJson) {
        const saved = await persistFramework(accessToken, opportunityId, frameworkJson);
        setFrameworkVersion(saved);
        setFrameworkJson(saved.framework_json);
        setDirty(false);
        const nextReview = await applyReview(saved);
        if (nextReview && isApprovalBlocked(nextReview)) {
          setError(
            "This customer story still has issues that must be resolved before the presentation can be built.",
          );
          return;
        }
      }
      const confirmed = await confirmFramework(accessToken, opportunityId);
      setFrameworkVersion(confirmed);
      setFrameworkJson(confirmed.framework_json);
      setDirty(false);
      setHumanConfirmed(false);
      await applyReview(confirmed);
      setInfo("Approved. Building the presentation plan…");
      try {
        await generatePresentationPlan(accessToken, opportunityId, confirmed.id);
      } catch {
        // Plan generation can continue from the next step if enqueue fails.
      }
      router.push(pipelineHref("/plan-preview", opportunityId));
    } catch (confirmError) {
      setError(confirmError instanceof Error ? confirmError.message : "Approval failed.");
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
              <p>Sign in to review and edit the framework for this opportunity.</p>
            </div>
            <div className="upload-banner-actions">
              <Link href="/login" className="btn btn-primary">
                Sign in
              </Link>
            </div>
          </div>
        ) : null}

        <PipelineStepper
          currentStep={2}
          opportunityId={opportunityId}
          frameworkReady={Boolean(frameworkVersion)}
          frameworkConfirmed={frameworkConfirmed}
        />
        <AppPageHeader
          kicker="Step 2 of 4"
          title="Review the customer story"
          lead="Start with the summary, resolve anything that needs attention, then approve to build the presentation. All 14 chapters stay available below for review and editing."
        />

        <div className="upload-layout">
          <aside className="upload-sidebar">
            <div className="upload-meta-card">
              <h3>Active opportunity</h3>
              <p className="upload-meta-empty">
                {frameworkConfirmed
                  ? "This customer story is approved. Continue to the presentation."
                  : "Approve only after you have reviewed the summary and any warnings."}
              </p>
              <Link href={pipelineHref("/upload", opportunityId)} className="btn btn-secondary btn-block">
                Back to upload
              </Link>
              {frameworkConfirmed ? (
                <Link
                  href={pipelineHref("/plan-preview", opportunityId)}
                  className="btn btn-primary btn-block"
                >
                  Continue to presentation
                </Link>
              ) : (
                <a href="#framework-chapters" className="btn btn-secondary btn-block">
                  Review all 14 chapters
                </a>
              )}
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

            {busy && !frameworkVersion ? (
              <section className="upload-panel pipeline-panel-loading">
                <p className="upload-hint" data-testid="pipeline-job-progress">
                  {info ?? "Loading customer story…"}
                </p>
              </section>
            ) : null}

            {!busy && !frameworkVersion && isAuthenticated ? (
              <section className="upload-panel pipeline-empty-panel">
                <header className="upload-panel-header">
                  <div>
                    <h2>Generate the customer story</h2>
                    <p>
                      After transcripts are uploaded, generate the 14-chapter customer report.
                      Review the summary first, then inspect chapters and cited sources before you
                      approve.
                    </p>
                  </div>
                </header>
                <div className="pipeline-empty-body">
                  <div className="pipeline-empty-icon" aria-hidden="true">
                    14
                  </div>
                  {(transcriptCount ?? 0) === 0 ? (
                    <>
                      <p>
                        No transcripts are attached to this opportunity yet. Upload at least one
                        discovery transcript, then generate the customer story.
                      </p>
                      <Link
                        href={pipelineHref("/upload", opportunityId)}
                        className="btn btn-primary"
                      >
                        Back to upload
                      </Link>
                    </>
                  ) : (
                    <>
                      <p>
                        {transcriptCount} transcript{transcriptCount === 1 ? "" : "s"} ready.
                        Generate the 14-chapter draft to review it here.
                      </p>
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={busy}
                        onClick={() => void handleGenerate()}
                      >
                        Generate customer story
                      </button>
                    </>
                  )}
                </div>
              </section>
            ) : null}

            {frameworkVersion && frameworkJson ? (
              <>
                <section className="upload-panel">
                  <header className="upload-panel-header">
                    <div>
                      <h2>Customer story summary</h2>
                      <p>
                        Version {frameworkVersion.version_number} ·{" "}
                        <span className="framework-status-pill">
                          {customerStatusLabel(frameworkVersion.status)}
                        </span>
                      </p>
                    </div>
                    <div className="framework-toolbar-actions">
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={busy || downloadingFormat !== null}
                        onClick={() => void handleDownloadFramework("docx")}
                      >
                        {downloadingFormat === "docx" ? "Downloading…" : "Download Word"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={busy || downloadingFormat !== null}
                        onClick={() => void handleDownloadFramework("pdf")}
                      >
                        {downloadingFormat === "pdf" ? "Downloading…" : "Download PDF"}
                      </button>
                    </div>
                  </header>

                  <div className="framework-meta-grid">
                    <div className="form-field">
                      <label htmlFor="framework-title">Title</label>
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

                  {review ? (
                    <FrameworkReviewSummary
                      review={review}
                      editable={editable}
                      confirmed={frameworkConfirmed}
                      busy={busy || downloadingFormat !== null}
                      dirty={dirty}
                      humanConfirmed={humanConfirmed}
                      onHumanConfirmedChange={setHumanConfirmed}
                      onApprove={() => void handleApprove()}
                      onSave={() => void handleSave()}
                      onJumpToChapter={jumpToChapter}
                    />
                  ) : (
                    <div className="framework-approve-panel">
                      <p className="upload-hint">
                        The concise summary is not available yet. Review the 14 chapters below
                        before approving.
                      </p>
                      {editable && !frameworkConfirmed ? (
                        <>
                          <label className="framework-human-confirm">
                            <input
                              type="checkbox"
                              data-testid="framework-human-confirm"
                              checked={humanConfirmed}
                              disabled={busy}
                              onChange={(event) => setHumanConfirmed(event.target.checked)}
                            />
                            <span>
                              I have reviewed this customer story and I approve building the
                              presentation.
                            </span>
                          </label>
                          <button
                            type="button"
                            className="btn btn-primary"
                            data-testid="framework-approve-button"
                            disabled={
                              busy ||
                              !canApproveAndBuild({
                                editable,
                                confirmed: frameworkConfirmed,
                                humanConfirmed,
                                blocked: false,
                              })
                            }
                            onClick={() => void handleApprove()}
                          >
                            Approve & build presentation
                          </button>
                        </>
                      ) : null}
                    </div>
                  )}

                  <div className="framework-export-panel" data-testid="framework-export-panel">
                    <div>
                      <strong>Download the customer report</strong>
                      <p>
                        Export the complete 14-chapter report as Word or PDF. Draft versions are
                        labeled until you approve.
                      </p>
                    </div>
                    <div className="framework-toolbar-actions">
                      <button
                        type="button"
                        className="btn btn-secondary"
                        data-testid="framework-download-word"
                        disabled={busy || downloadingFormat !== null}
                        onClick={() => void handleDownloadFramework("docx")}
                      >
                        {downloadingFormat === "docx" ? "Downloading…" : "Download Word"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        data-testid="framework-download-pdf"
                        disabled={busy || downloadingFormat !== null}
                        onClick={() => void handleDownloadFramework("pdf")}
                      >
                        {downloadingFormat === "pdf" ? "Downloading…" : "Download PDF"}
                      </button>
                    </div>
                  </div>
                </section>

                <details className="framework-details-disclosure">
                  <summary>Additional structured details</summary>
                  <FrameworkRootFieldsPanel
                    framework={frameworkJson}
                    editable={editable && !busy}
                    onChange={applyFrameworkDraft}
                  />
                </details>

                <div className="framework-layout" id="framework-chapters">
                  <aside className="framework-sidebar">
                    <h2>All 14 chapters</h2>
                    <ol className="framework-chapter-nav">
                      {chapterNav.map((item) => {
                        const isHighlighted = highlightedChapterId === item.chapterId;
                        return (
                          <li key={item.chapterId}>
                            <a
                              ref={(node) => {
                                chapterNavItemRefs.current[item.chapterId] = node;
                              }}
                              href={`#framework-chapter-${item.chapterId}`}
                              className={
                                isHighlighted
                                  ? "framework-chapter-nav-btn framework-chapter-nav-btn-active"
                                  : "framework-chapter-nav-btn"
                              }
                              aria-current={isHighlighted ? "true" : undefined}
                              onClick={() => setActiveChapterId(item.chapterId)}
                            >
                              <span>Chapter {item.chapterId}</span>
                              <span>{item.title}</span>
                              {item.refCount > 0 ? (
                                <span className="framework-ref-count">
                                  {item.refCount} cited source{item.refCount === 1 ? "" : "s"}
                                </span>
                              ) : null}
                            </a>
                          </li>
                        );
                      })}
                    </ol>
                  </aside>

                  <div
                    className="framework-main framework-all-chapters"
                    onMouseLeave={() => setHoveredChapterId(null)}
                  >
                    {frameworkJson.chapters.map((chapter, chapterIndex) => (
                      <div
                        key={chapter.chapter_id}
                        id={`framework-chapter-${chapter.chapter_id}`}
                        className={
                          highlightedChapterId === chapter.chapter_id
                            ? "framework-chapter-anchor framework-chapter-anchor-active"
                            : "framework-chapter-anchor"
                        }
                        onMouseEnter={() => setHoveredChapterId(chapter.chapter_id)}
                      >
                        <FrameworkChapterView
                          chapter={chapter}
                          editable={editable && !busy}
                          regenerating={regeneratingChapterId === chapter.chapter_id}
                          onRegenerate={
                            editable
                              ? () => void handleRegenerateChapter(chapter.chapter_id)
                              : undefined
                          }
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

