"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { useAuth } from "@/components/AuthProvider";
import { FrameworkChapterView } from "@/components/FrameworkChapterView";
import { FrameworkRootFieldsPanel } from "@/components/FrameworkRootFieldsPanel";
import { PipelineStepper } from "@/components/PipelineStepper";
import { RecoveryBanner } from "@/components/RecoveryBanner";
import { SiteHeader } from "@/components/SiteHeader";
import {
  ApiRequestError,
  FRAMEWORK_JOB_TIMEOUT_MS,
  confirmFramework,
  downloadFrameworkRender,
  generateFramework,
  getActiveJob,
  getJob,
  getLatestFramework,
  listTranscripts,
  regenerateFrameworkChapter,
  retryJob,
  updateFramework as persistFramework,
  waitForJob,
} from "@/lib/api";
import { startFrameworkReviewParallelLoad } from "@/lib/frameworkReviewLoad";
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
import type { FrameworkObject, FrameworkVersionResponse } from "@/lib/frameworkTypes";
import {
  inputRequiredRecoveryNotice,
  jobFailureRecoveryNotice,
  recoveryActionHref,
  recoveryNoticeFromError,
  retryingRecoveryNotice,
  runningRecoveryNotice,
} from "@/lib/recoveryUx";
import type { RecoveryNotice } from "@/lib/recoveryUx";

interface FrameworkReviewPanelProps {
  opportunityId: string;
}

export function FrameworkReviewPanel({ opportunityId }: FrameworkReviewPanelProps) {
  const { accessToken, isAuthenticated, loading, session } = useAuth();
  const [frameworkVersion, setFrameworkVersion] = useState<FrameworkVersionResponse | null>(null);
  const [frameworkJson, setFrameworkJson] = useState<FrameworkObject | null>(null);
  const [busy, setBusy] = useState(false);
  const [frameworkLoading, setFrameworkLoading] = useState(true);
  const [jobPolling, setJobPolling] = useState(false);
  const [jobStage, setJobStage] = useState<string | null>(null);
  const [notice, setNotice] = useState<RecoveryNotice | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [regeneratingChapterId, setRegeneratingChapterId] = useState<string | null>(null);
  const [retryJobId, setRetryJobId] = useState<string | null>(null);
  const [recoveryTarget, setRecoveryTarget] = useState<
    | "job"
    | "save"
    | "download-docx"
    | "download-pdf"
    | "regenerate-save"
    | "regenerate-enqueue"
    | "confirm-save"
    | "confirm"
  >("job");
  const [recoveryChapterId, setRecoveryChapterId] = useState<string | null>(null);
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

  const applyLatestFramework = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const latest = await getLatestFramework(accessToken, opportunityId);
      setFrameworkVersion(latest);
      setFrameworkJson(latest.framework_json);
      setDirty(false);
    } catch (loadError) {
      setFrameworkVersion(null);
      setFrameworkJson(null);
      if (!isMissingFrameworkError(loadError)) {
        throw loadError;
      }
    }
  }, [accessToken, opportunityId]);

  const loadFramework = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      await applyLatestFramework();
    } catch (loadError) {
      setNotice(recoveryNoticeFromError(loadError, "framework"));
    } finally {
      setBusy(false);
    }
  }, [accessToken, applyLatestFramework]);

  useEffect(() => {
    if (loading || !accessToken) {
      return;
    }
    const token = accessToken;
    setFrameworkLoading(true);
    setJobPolling(false);
    setJobStage(null);
    setNotice(null);
    setInfo(null);
    setRetryJobId(null);

    const cancel = startFrameworkReviewParallelLoad(
      {
        onFrameworkLoaded: (latest) => {
          setFrameworkVersion(latest);
          setFrameworkJson(latest.framework_json);
          setDirty(false);
        },
        onFrameworkMissing: () => {
          setFrameworkVersion(null);
          setFrameworkJson(null);
        },
        onFrameworkLoadFinished: () => {
          setFrameworkLoading(false);
        },
        onFrameworkLoadError: (message) => {
          setNotice(recoveryNoticeFromError(new Error(message), "framework"));
        },
        onJobPollingStart: (message, stage, jobId) => {
          setJobPolling(true);
          setInfo(message);
          setJobStage(stage);
          setNotice(runningRecoveryNotice("framework", jobId));
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
              "framework",
            ),
          );
          setRetryJobId(failedJobId);
        },
      },
      {
        loadFramework: () => getLatestFramework(token, opportunityId),
        getActiveJob: () => getActiveJob(token, opportunityId, stageGroupForPage("framework")),
        getJob: (jobId) => getJob(token, jobId),
      },
    );

    return cancel;
  }, [accessToken, loading, opportunityId]);

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

  async function handleGenerate() {
    if (!accessToken) {
      return;
    }
    if ((transcriptCount ?? 0) === 0) {
      setNotice(inputRequiredRecoveryNotice("framework"));
      return;
    }
    setRecoveryTarget("job");
    setBusy(true);
    setNotice(null);
    setInfo(null);
    setRetryJobId(null);
    try {
      const generated = await generateFramework(accessToken, opportunityId);
      setInfo(generationProgressMessage("framework", Boolean(generated.is_existing_job)));
      setNotice(runningRecoveryNotice("framework", generated.job_id));
      await waitForJob(accessToken, generated.job_id, FRAMEWORK_JOB_TIMEOUT_MS);
      setNotice(null);
      await loadFramework();
    } catch (generateError) {
      setInfo(null);
      setNotice(recoveryNoticeFromError(generateError, "framework"));
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
    setNotice(retryingRecoveryNotice("framework", retryJobId));
    setInfo("Retrying generation from the last failed stage…");
    try {
      const queued = await retryJob(accessToken, retryJobId);
      setRetryJobId(null);
      await waitForJob(accessToken, queued.job_id, FRAMEWORK_JOB_TIMEOUT_MS);
      setNotice(null);
      await loadFramework();
    } catch (retryError) {
      setInfo(null);
      setNotice(recoveryNoticeFromError(retryError, "framework"));
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
    setNotice(runningRecoveryNotice("framework"));
    try {
      const job = await getActiveJob(
        accessToken,
        opportunityId,
        stageGroupForPage("framework"),
      );
      const decision = inspectActiveJob(job, "framework");
      if (decision.action === "failed") {
        setRetryJobId(decision.retryable ? decision.jobId : null);
        setNotice(jobFailureRecoveryNotice(decision.error, "framework", decision.jobId));
        return;
      }
      if (decision.action === "monitor") {
        setNotice(runningRecoveryNotice("framework", decision.jobId));
        await waitForJob(accessToken, decision.jobId, FRAMEWORK_JOB_TIMEOUT_MS);
      }
      await applyLatestFramework();
      setNotice(null);
    } catch (reconnectError) {
      setNotice(recoveryNoticeFromError(reconnectError, "framework"));
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

  async function handleConfirmReconnect() {
    setBusy(true);
    setInfo(null);
    try {
      await applyLatestFramework();
      setNotice(null);
    } catch (reconnectError) {
      setNotice(
        recoveryNoticeFromError(reconnectError, "framework", {
          connectionMessage: "We could not confirm the latest framework status. Reconnect to check again.",
        }),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerateReconnect(chapterId: string) {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setInfo(null);
    setNotice(runningRecoveryNotice("framework"));
    try {
      const job = await getActiveJob(
        accessToken,
        opportunityId,
        stageGroupForPage("framework"),
      );
      if (!job || job.job_type !== "framework_regenerate_chapter") {
        setBusy(false);
        await handleRegenerateChapter(chapterId);
        return;
      }
      const decision = inspectActiveJob(job, "framework");
      if (decision.action === "failed") {
        setRetryJobId(decision.retryable ? decision.jobId : null);
        setRecoveryTarget("job");
        setNotice(jobFailureRecoveryNotice(decision.error, "framework", decision.jobId));
        return;
      }
      if (decision.action === "monitor") {
        setRecoveryTarget("job");
        setNotice(runningRecoveryNotice("framework", decision.jobId));
        await waitForJob(accessToken, decision.jobId, FRAMEWORK_JOB_TIMEOUT_MS);
      }
      await applyLatestFramework();
      setNotice({
        category: "INPUT_REQUIRED",
        title: "Check the regenerated chapter",
        message: `We restored the latest framework after the connection interruption. Review chapter ${chapterId}; if its update is missing, regenerate it again.`,
        action: {
          kind: "REVIEW",
          label: "Review chapter",
          target: "framework",
          href: `#framework-chapter-${chapterId}`,
        },
      });
    } catch (reconnectError) {
      setNotice(recoveryNoticeFromError(reconnectError, "framework"));
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
      if (recoveryTarget === "save") {
        void handleSave();
        return;
      }
      if (recoveryTarget === "download-docx") {
        void handleDownloadFramework("docx");
        return;
      }
      if (recoveryTarget === "download-pdf") {
        void handleDownloadFramework("pdf");
        return;
      }
      if (recoveryTarget === "confirm-save") {
        void handleConfirm();
        return;
      }
      if (recoveryTarget === "confirm") {
        void handleConfirmReconnect();
        return;
      }
      if (recoveryTarget === "regenerate-save" && recoveryChapterId) {
        void handleRegenerateChapter(recoveryChapterId);
        return;
      }
      if (recoveryTarget === "regenerate-enqueue" && recoveryChapterId) {
        void handleRegenerateReconnect(recoveryChapterId);
        return;
      }
      void handleReconnect();
    }
  }

  async function handleSave() {
    if (!accessToken || !frameworkJson) {
      return;
    }
    setRecoveryTarget("save");
    setBusy(true);
    setNotice(null);
    setInfo(null);
    try {
      const saved = await persistFramework(accessToken, opportunityId, frameworkJson);
      setFrameworkVersion(saved);
      setFrameworkJson(saved.framework_json);
      setDirty(false);
      setInfo("Changes saved.");
    } catch (saveError) {
      setNotice(
        recoveryNoticeFromError(saveError, "framework", {
          connectionMessage: "Your changes were not saved. Reconnect to try saving them again.",
        }),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDownloadFramework(format: "docx" | "pdf") {
    if (!accessToken || !frameworkVersion || !frameworkJson) {
      return;
    }
    setRecoveryTarget(format === "docx" ? "download-docx" : "download-pdf");
    setDownloadingFormat(format);
    setNotice(null);
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
      setNotice(
        recoveryNoticeFromError(downloadError, "framework", {
          connectionMessage: "The download was interrupted. Reconnect to try it again.",
        }),
      );
    } finally {
      setDownloadingFormat(null);
    }
  }

  async function handleRegenerateChapter(chapterId: string) {
    if (!accessToken) {
      return;
    }
    setRecoveryTarget("regenerate-save");
    setRecoveryChapterId(chapterId);
    setBusy(true);
    setRegeneratingChapterId(chapterId);
    setNotice(null);
    setInfo(null);
    try {
      if (dirty && frameworkJson) {
        await persistFramework(accessToken, opportunityId, frameworkJson);
      }
      setRecoveryTarget("regenerate-enqueue");
      const queued = await regenerateFrameworkChapter(accessToken, opportunityId, chapterId);
      setRecoveryTarget("job");
      setInfo(`Regenerating chapter ${chapterId}…`);
      await waitForJob(accessToken, queued.job_id, FRAMEWORK_JOB_TIMEOUT_MS);
      await loadFramework();
      setInfo(`Chapter ${chapterId} regeneration finished. Other chapters were left unchanged.`);
    } catch (regenerateError) {
      setNotice(recoveryNoticeFromError(regenerateError, "framework"));
    } finally {
      setRegeneratingChapterId(null);
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!accessToken) {
      return;
    }
    setRecoveryTarget("confirm-save");
    setBusy(true);
    setNotice(null);
    setInfo(null);
    try {
      if (dirty && frameworkJson) {
        await persistFramework(accessToken, opportunityId, frameworkJson);
      }
      setRecoveryTarget("confirm");
      const confirmed = await confirmFramework(accessToken, opportunityId);
      setFrameworkVersion(confirmed);
      setFrameworkJson(confirmed.framework_json);
      setDirty(false);
      setInfo("Framework confirmed. You can preview the presentation plan next.");
    } catch (confirmError) {
      setNotice(
        recoveryNoticeFromError(confirmError, "framework", {
          connectionMessage: "The framework was not confirmed. Reconnect to try again.",
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
          title="Framework review"
          lead="Review all 14 chapters, inspect source references, and edit any field while the framework is draft or in review. Confirmation locks the object."
        />

        <div className="upload-layout">
          <aside className="upload-sidebar">
            <div className="upload-meta-card">
              <h3>Active opportunity</h3>
              <p className="upload-meta-empty">Continue when the 14-chapter draft is ready to lock.</p>
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

          <div className="upload-main" id="framework-review-content">
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

            {frameworkLoading && !frameworkVersion ? (
              <section className="upload-panel pipeline-panel-loading">
                <p className="upload-hint" data-testid="framework-loading">
                  Loading framework…
                </p>
              </section>
            ) : null}

            {jobPolling ? (
              <section className="upload-panel pipeline-panel-loading">
                <p className="upload-hint" data-testid="pipeline-job-progress">
                  {info ?? "Framework generation is running…"}
                  {jobStage ? ` · ${jobStage.replaceAll("_", " ").toLowerCase()}` : ""}
                </p>
              </section>
            ) : null}

            {!frameworkLoading && !frameworkVersion && isAuthenticated && !notice ? (
              <section className="upload-panel pipeline-empty-panel">
                <header className="upload-panel-header">
                  <div>
                    <h2>Generate the framework draft</h2>
                    <p>
                      After transcripts are uploaded, generate the 14-chapter Customer Framework
                      Report. You can review source references, edit every field, or regenerate a
                      single chapter before confirming.
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
                        discovery transcript, then generate the framework.
                      </p>
                      <Link
                        href={`/upload?opportunityId=${opportunityId}`}
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
                        Generate framework
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
                      <h2>Framework summary</h2>
                      <p>
                        Version {frameworkVersion.version_number} · status{" "}
                        <span className="framework-status-pill">{frameworkVersion.status}</span>
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
                      {editable ? (
                        <>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            disabled={busy || !dirty || downloadingFormat !== null}
                            onClick={() => void handleSave()}
                          >
                            Save changes
                          </button>
                          <button
                            type="button"
                            className="btn btn-primary"
                            disabled={busy || downloadingFormat !== null}
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

                  <div className="framework-export-panel" data-testid="framework-export-panel">
                    <div>
                      <strong>Export framework report</strong>
                      <p>
                        Download the complete 14-chapter framework as Word or PDF. Draft versions
                        are labeled accordingly until you confirm.
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

                {frameworkConfirmed && !notice ? (
                  <div className="upload-banner upload-banner-info">
                    <div>
                      <strong>Framework confirmed</strong>
                      <p>
                        This version is locked. Fields, source references, and chapter regenerate
                        stay read-only so Stage B can only use the confirmed object.
                      </p>
                    </div>
                  </div>
                ) : null}

                <FrameworkRootFieldsPanel
                  framework={frameworkJson}
                  editable={editable && !busy}
                  onChange={applyFrameworkDraft}
                />

                <div className="framework-layout">
                  <aside className="framework-sidebar">
                    <h2>Chapters</h2>
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
                              <span>{item.chapterId}</span>
                              <span>{item.title}</span>
                              {item.refCount > 0 ? (
                                <span className="framework-ref-count">{item.refCount} refs</span>
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

