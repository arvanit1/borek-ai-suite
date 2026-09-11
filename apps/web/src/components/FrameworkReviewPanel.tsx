"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { useAuth } from "@/components/AuthProvider";
import { FrameworkChapterView } from "@/components/FrameworkChapterView";
import { JourneyStageChoice } from "@/components/JourneyStageSelector";
import { FrameworkReviewSummary } from "@/components/FrameworkReviewSummary";
import { FrameworkRootFieldsPanel } from "@/components/FrameworkRootFieldsPanel";
import { LiveGenerationProgress } from "@/components/LiveGenerationProgress";
import { RecoveryBanner } from "@/components/RecoveryBanner";
import { SiteHeader } from "@/components/SiteHeader";
import { WorkflowActionBar } from "@/components/WorkflowActionBar";
import {
  ApiRequestError,
  FRAMEWORK_JOB_TIMEOUT_MS,
  confirmFramework,
  downloadFrameworkRender,
  generateFramework,
  generatePresentationPlan,
  getActiveJob,
  getFrameworkReview,
  getJob,
  getLatestFramework,
  getLatestPresentationPlan,
  getPresentation,
  getPresentationPlan,
  listTranscripts,
  regenerateFrameworkChapter,
  retryJob,
  updateFramework as persistFramework,
  waitForJob,
} from "@/lib/api";
import type { JobResponse } from "@/lib/api";
import { startFrameworkReviewParallelLoad } from "@/lib/frameworkReviewLoad";
import {
  buildFrameworkDownloadFilename,
  buildFrameworkRenderPath,
} from "@/lib/frameworkExport";
import { isMissingFrameworkError } from "@/lib/apiErrors";
import {
  buildJobProgressView,
  jobStageLabel,
  snapshotFromJob,
  type JobProgressSnapshot,
} from "@/lib/jobProgress";
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
import { journeyStageForGenerate } from "@/lib/journeyStageSelection";
import { pipelineHref } from "@/lib/pipelineContext";
import type { FrameworkObject, FrameworkVersionResponse } from "@/lib/frameworkTypes";
import {
  PresentationPipelineError,
  approveAndBuildPresentation,
  deckResultHref,
  recoverPresentationPipeline,
} from "@/lib/presentationPipeline";
import type {
  PresentationPipelineApi,
  PresentationPipelineProgress,
  PresentationPipelineResult,
} from "@/lib/presentationPipeline";
import {
  inputRequiredRecoveryNotice,
  jobFailureRecoveryNotice,
  recoveryActionHref,
  recoveryNoticeFromError,
  recoverySurfacePrecedence,
  retryingRecoveryNotice,
  runningRecoveryNotice,
} from "@/lib/recoveryUx";
import type { RecoveryNotice } from "@/lib/recoveryUx";

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
  const [frameworkLoading, setFrameworkLoading] = useState(true);
  const [jobPolling, setJobPolling] = useState(false);
  const [jobStage, setJobStage] = useState<string | null>(null);
  const [frameworkJobSnapshot, setFrameworkJobSnapshot] = useState<JobProgressSnapshot | null>(
    null,
  );
  const [pipelineJobSnapshot, setPipelineJobSnapshot] = useState<JobProgressSnapshot | null>(null);
  const [pipelineHandoff, setPipelineHandoff] = useState(false);
  const [pipelineActive, setPipelineActive] = useState(false);
  const [plannedSlideCount, setPlannedSlideCount] = useState<number | null>(null);
  const [notice, setNotice] = useState<RecoveryNotice | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [humanConfirmed, setHumanConfirmed] = useState(false);
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
    | "presentation-pipeline"
  >("job");
  const [recoveryChapterId, setRecoveryChapterId] = useState<string | null>(null);
  const [transcriptCount, setTranscriptCount] = useState<number | null>(null);
  const [activeChapterId, setActiveChapterId] = useState<string | null>(null);
  const [downloadingFormat, setDownloadingFormat] = useState<"docx" | "pdf" | null>(null);
  const [downloadLanguage, setDownloadLanguage] = useState("en");
  const presentationPipelineRunningRef = useRef(false);
  const presentationRecoveryAttemptedRef = useRef<string | null>(null);

  const editable = frameworkVersion
    ? canEditFramework(frameworkVersion.status, frameworkJson?.status)
    : false;
  const frameworkConfirmed = Boolean(
    frameworkVersion &&
      (isFrameworkConfirmed(frameworkVersion.status) ||
        (frameworkJson != null && isFrameworkConfirmed(frameworkJson.status))),
  );

  const presentationPipelineApi = useCallback(
    (token: string): PresentationPipelineApi => ({
      getActivePresentationJob: () => getActiveJob(token, opportunityId, "presentation"),
      getJob: (jobId) => getJob(token, jobId),
      waitForJob: (jobId, onJobUpdate) => waitForJob(token, jobId, { onProgress: onJobUpdate }),
      generatePresentationPlan: (frameworkVersionId, autoContinue) =>
        generatePresentationPlan(
          token,
          opportunityId,
          frameworkVersionId,
          autoContinue,
          journeyStageForGenerate(opportunityId),
        ),
      getLatestPresentationPlan: () => getLatestPresentationPlan(token, opportunityId),
      getPresentationPlan: (presentationPlanId) =>
        getPresentationPlan(token, presentationPlanId),
      getPresentation: (presentationId) => getPresentation(token, presentationId),
    }),
    [opportunityId],
  );

  const reportPresentationProgress = useCallback((progress: PresentationPipelineProgress) => {
    setRecoveryTarget("presentation-pipeline");
    // The live progress panel owns in-flight messaging; banners are for recovery only.
    setNotice(null);
    setInfo(null);
    if (progress.state === "running") {
      setPipelineJobSnapshot(progress.job);
      setPipelineHandoff(false);
      return;
    }
    if (progress.state === "handoff") {
      setPipelineHandoff(true);
      return;
    }
    if (progress.state === "completed" && progress.phase === "planning") {
      setPlannedSlideCount(progress.plannedSlideCount);
    }
  }, []);

  const trackFrameworkJob = useCallback((job: JobResponse) => {
    setFrameworkJobSnapshot(snapshotFromJob(job));
  }, []);

  const frameworkProgressView = useMemo(
    () => buildJobProgressView({ snapshot: frameworkJobSnapshot }),
    [frameworkJobSnapshot],
  );

  const pipelineProgressView = useMemo(
    () =>
      buildJobProgressView({
        snapshot: pipelineJobSnapshot,
        handoff: pipelineHandoff,
        plannedSlideCount,
      }),
    [pipelineHandoff, pipelineJobSnapshot, plannedSlideCount],
  );

  const liveProgressView = pipelineProgressView ?? frameworkProgressView;
  const liveProgressVisible = Boolean(
    liveProgressView && (pipelineActive || jobPolling || liveProgressView.failed),
  );

  const openPresentationResult = useCallback(
    (result: PresentationPipelineResult) => {
      router.push(deckResultHref(opportunityId, result));
    },
    [opportunityId, router],
  );

  const reportPresentationFailure = useCallback((error: unknown) => {
    const pipelineError =
      error instanceof PresentationPipelineError
        ? error
        : new PresentationPipelineError("generation", "Presentation generation failed");
    const context = pipelineError.phase === "generation" ? "deck" : "plan";
    const recovered = recoveryNoticeFromError(pipelineError, context);
    setInfo(null);
    setRetryJobId(
      recovered.action?.kind === "RETRY" && pipelineError.jobId ? pipelineError.jobId : null,
    );
    setRecoveryTarget("presentation-pipeline");
    setNotice({
      ...recovered,
      action: recovered.action ??
        (pipelineError.phase === "generation"
          ? {
              kind: "REVIEW",
              label: "View presentation structure",
              target: "plan",
            }
          : {
              kind: "REVIEW",
              label: "Review confirmed framework",
              target: "framework",
            }),
    });
  }, []);

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

  const applyLatestFramework = useCallback(async (): Promise<FrameworkVersionResponse | null> => {
    if (!accessToken) {
      return null;
    }
    try {
      const latest = await getLatestFramework(accessToken, opportunityId);
      setFrameworkVersion(latest);
      setFrameworkJson(latest.framework_json);
      setDirty(false);
      setHumanConfirmed(false);
      await applyReview(latest);
      return latest;
    } catch (loadError) {
      setFrameworkVersion(null);
      setFrameworkJson(null);
      setReview(null);
      if (!isMissingFrameworkError(loadError)) {
        throw loadError;
      }
      return null;
    }
  }, [accessToken, applyReview, opportunityId]);

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

  const recoverConfirmedPresentation = useCallback(
    async (framework: FrameworkVersionResponse) => {
      if (!accessToken || presentationPipelineRunningRef.current) {
        return;
      }
      presentationPipelineRunningRef.current = true;
      setRecoveryTarget("presentation-pipeline");
      setBusy(true);
      try {
        const recovery = await recoverPresentationPipeline({
          frameworkVersionId: framework.id,
          api: presentationPipelineApi(accessToken),
          onProgress: (progress) => {
            setPipelineActive(true);
            reportPresentationProgress(progress);
          },
        });
        if (recovery.state === "completed") {
          setNotice(null);
          openPresentationResult(recovery.result);
        }
      } catch (error) {
        reportPresentationFailure(error);
      } finally {
        presentationPipelineRunningRef.current = false;
        setPipelineActive(false);
        setBusy(false);
      }
    },
    [
      accessToken,
      openPresentationResult,
      presentationPipelineApi,
      reportPresentationFailure,
      reportPresentationProgress,
    ],
  );

  useEffect(() => {
    if (loading || !accessToken) {
      return;
    }
    const token = accessToken;
    setFrameworkLoading(true);
    setJobPolling(false);
    setJobStage(null);
    setFrameworkJobSnapshot(null);
    setNotice(null);
    setInfo(null);
    setRetryJobId(null);

    const cancel = startFrameworkReviewParallelLoad(
      {
        onFrameworkLoaded: (latest) => {
          setFrameworkVersion(latest);
          setFrameworkJson(latest.framework_json);
          setDirty(false);
          void applyReview(latest);
        },
        onFrameworkMissing: () => {
          setFrameworkVersion(null);
          setFrameworkJson(null);
          setReview(null);
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
        onJobSnapshot: setFrameworkJobSnapshot,
        onJobPollingFinished: () => {
          setJobPolling(false);
          setInfo(null);
          setJobStage(null);
          setFrameworkJobSnapshot(null);
          setNotice(null);
        },
        onJobFailed: (error, failedJobId) => {
          setNotice(recoveryNoticeFromError(error, "framework"));
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
  }, [accessToken, applyReview, loading, opportunityId]);

  useEffect(() => {
    if (
      !frameworkVersion ||
      !frameworkConfirmed ||
      presentationRecoveryAttemptedRef.current === frameworkVersion.id
    ) {
      return;
    }
    presentationRecoveryAttemptedRef.current = frameworkVersion.id;
    void recoverConfirmedPresentation(frameworkVersion);
  }, [frameworkConfirmed, frameworkVersion, recoverConfirmedPresentation]);

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

  useEffect(() => {
    if (!chapterIdsKey) {
      setActiveChapterId(null);
      return;
    }

    const ids = chapterIdsKey.split("|");
    const hashPrefix = "#framework-chapter-";
    const openChapterFromLocation = (moveFocus = false) => {
      if (!window.location.hash.startsWith(hashPrefix)) {
        setActiveChapterId((current) => {
          if (moveFocus && current) {
            window.requestAnimationFrame(() => {
              document.getElementById(`framework-chapter-button-${current}`)?.focus();
            });
          }
          return null;
        });
        return;
      }
      let chapterId: string;
      try {
        chapterId = decodeURIComponent(window.location.hash.slice(hashPrefix.length));
      } catch {
        return;
      }
      if (ids.includes(chapterId)) {
        setActiveChapterId(chapterId);
        window.requestAnimationFrame(() => {
          document
            .getElementById(`framework-chapter-${chapterId}`)
            ?.scrollIntoView({ behavior: "smooth", block: "start" });
          if (moveFocus) {
            document.getElementById(`framework-chapter-button-${chapterId}`)?.focus();
          }
        });
      }
    };
    const handleHistoryChange = () => openChapterFromLocation(true);

    setActiveChapterId((current) => (current && ids.includes(current) ? current : null));
    openChapterFromLocation();
    window.addEventListener("hashchange", handleHistoryChange);
    window.addEventListener("popstate", handleHistoryChange);
    return () => {
      window.removeEventListener("hashchange", handleHistoryChange);
      window.removeEventListener("popstate", handleHistoryChange);
    };
  }, [chapterIdsKey]);

  function applyFrameworkDraft(next: FrameworkObject) {
    setFrameworkJson(next);
    setDirty(true);
    setHumanConfirmed(false);
    if (notice?.category === "VALIDATION_NEEDS_REVIEW") {
      setNotice(null);
    }
  }

  function openChapter(chapterId: string, moveFocus = false) {
    setActiveChapterId(chapterId);
    const url = new URL(window.location.href);
    url.hash = `framework-chapter-${encodeURIComponent(chapterId)}`;
    window.history.pushState(null, "", url);
    window.requestAnimationFrame(() => {
      const node = document.getElementById(`framework-chapter-${chapterId}`);
      node?.scrollIntoView({ behavior: "smooth", block: "start" });
      if (moveFocus) {
        document.getElementById(`framework-chapter-button-${chapterId}`)?.focus();
      }
    });
  }

  function closeChapter(chapterId: string) {
    setActiveChapterId(null);
    if (window.location.hash === `#framework-chapter-${encodeURIComponent(chapterId)}`) {
      const url = new URL(window.location.href);
      url.hash = "";
      window.history.pushState(null, "", url);
    }
  }

  function jumpToChapter(chapterId: string) {
    openChapter(chapterId, true);
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
      setJobPolling(true);
      await waitForJob(accessToken, generated.job_id, {
        timeoutMs: FRAMEWORK_JOB_TIMEOUT_MS,
        onProgress: trackFrameworkJob,
      });
      setFrameworkJobSnapshot(null);
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
      setJobPolling(false);
    }
  }

  async function handleRetry() {
    if (!accessToken || !retryJobId) {
      return;
    }
    setRecoveryTarget("job");
    setFrameworkJobSnapshot(null);
    setPipelineJobSnapshot(null);
    setBusy(true);
    setNotice(retryingRecoveryNotice("framework", retryJobId));
    setInfo("Retrying generation from the last failed stage…");
    try {
      const queued = await retryJob(accessToken, retryJobId);
      setRetryJobId(null);
      setJobPolling(true);
      await waitForJob(accessToken, queued.job_id, {
        timeoutMs: FRAMEWORK_JOB_TIMEOUT_MS,
        onProgress: trackFrameworkJob,
      });
      if (recoveryTarget === "presentation-pipeline" && frameworkVersion) {
        await recoverConfirmedPresentation(frameworkVersion);
        return;
      }
      setFrameworkJobSnapshot(null);
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
      setJobPolling(false);
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
        setJobPolling(true);
        await waitForJob(accessToken, decision.jobId, {
          timeoutMs: FRAMEWORK_JOB_TIMEOUT_MS,
          onProgress: trackFrameworkJob,
        });
        setFrameworkJobSnapshot(null);
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
      setJobPolling(false);
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
        setJobPolling(true);
        await waitForJob(accessToken, decision.jobId, {
          timeoutMs: FRAMEWORK_JOB_TIMEOUT_MS,
          onProgress: trackFrameworkJob,
        });
        setFrameworkJobSnapshot(null);
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
      setJobPolling(false);
    }
  }

  function handleRecoveryAction() {
    if (notice?.action?.kind === "GENERATE") {
      void handleGenerate();
      return;
    }
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
        void handleDownloadFramework("docx", downloadLanguage);
        return;
      }
      if (recoveryTarget === "download-pdf") {
        void handleDownloadFramework("pdf");
        return;
      }
      if (recoveryTarget === "confirm-save") {
        void handleApprove();
        return;
      }
      if (recoveryTarget === "confirm") {
        void handleConfirmReconnect();
        return;
      }
      if (recoveryTarget === "presentation-pipeline" && frameworkVersion) {
        void recoverConfirmedPresentation(frameworkVersion);
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
      await applyReview(saved);
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

  async function handleDownloadFramework(format: "docx" | "pdf", language = "en") {
    if (!accessToken || !frameworkVersion || !frameworkJson) {
      return;
    }
    setDownloadLanguage(language);
    setRecoveryTarget(format === "docx" ? "download-docx" : "download-pdf");
    setDownloadingFormat(format);
    setNotice(null);
    try {
      const path = buildFrameworkRenderPath(frameworkVersion.id, format, language);
      const blob = await downloadFrameworkRender(accessToken, path);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = buildFrameworkDownloadFilename(frameworkJson.title, format, language);
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
    jumpToChapter(chapterId);
    try {
      if (dirty && frameworkJson) {
        await persistFramework(accessToken, opportunityId, frameworkJson);
      }
      setRecoveryTarget("regenerate-enqueue");
      const queued = await regenerateFrameworkChapter(accessToken, opportunityId, chapterId);
      setRecoveryTarget("job");
      setInfo(`Updating chapter ${chapterId}…`);
      setJobPolling(true);
      await waitForJob(accessToken, queued.job_id, {
        timeoutMs: FRAMEWORK_JOB_TIMEOUT_MS,
        onProgress: trackFrameworkJob,
      });
      setFrameworkJobSnapshot(null);
      await loadFramework();
      setInfo(`Chapter ${chapterId} was updated. Other chapters were left unchanged.`);
    } catch (regenerateError) {
      setNotice(recoveryNoticeFromError(regenerateError, "framework"));
    } finally {
      setRegeneratingChapterId(null);
      setBusy(false);
      setJobPolling(false);
    }
  }

  async function handleApproveAndBuild(alreadyConfirmed: boolean) {
    if (!accessToken || !frameworkVersion || presentationPipelineRunningRef.current) {
      return;
    }
    if (!alreadyConfirmed) {
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
    }
    setRecoveryTarget("confirm-save");
    setBusy(true);
    setNotice(null);
    setInfo(null);
    presentationPipelineRunningRef.current = true;
    setPipelineActive(true);
    setPipelineJobSnapshot(null);
    setPipelineHandoff(false);
    try {
      let currentFramework = frameworkVersion;
      if (dirty && frameworkJson) {
        currentFramework = await persistFramework(accessToken, opportunityId, frameworkJson);
        setFrameworkVersion(currentFramework);
        setFrameworkJson(currentFramework.framework_json);
        setDirty(false);
        const nextReview = await applyReview(currentFramework);
        if (nextReview && isApprovalBlocked(nextReview)) {
          setNotice({
            category: "VALIDATION_NEEDS_REVIEW",
            title: "Review is needed before continuing",
            message:
              "This customer story still has issues that must be resolved before the presentation can be built.",
            action: { kind: "REVIEW", label: "Review framework", target: "framework" },
          });
          return;
        }
      }
      setRecoveryTarget("confirm");
      const result = await approveAndBuildPresentation({
        alreadyConfirmed,
        frameworkVersionId: alreadyConfirmed ? currentFramework.id : undefined,
        confirmFramework: async () => {
          const confirmed = await confirmFramework(
            accessToken,
            opportunityId,
            currentFramework.id,
          );
          setFrameworkVersion(confirmed);
          setFrameworkJson(confirmed.framework_json);
          setDirty(false);
          setHumanConfirmed(false);
          presentationRecoveryAttemptedRef.current = confirmed.id;
          await applyReview(confirmed);
          return { id: confirmed.id, status: confirmed.status };
        },
        api: presentationPipelineApi(accessToken),
        onProgress: reportPresentationProgress,
      });
      setNotice(null);
      setInfo("Presentation is ready. Opening the deck…");
      openPresentationResult(result);
    } catch (pipelineError) {
      reportPresentationFailure(pipelineError);
    } finally {
      presentationPipelineRunningRef.current = false;
      setPipelineActive(false);
      setBusy(false);
    }
  }

  async function handleApprove() {
    await handleApproveAndBuild(false);
  }

  async function handleBuildConfirmedFramework() {
    await handleApproveAndBuild(true);
  }

  const progressSurfaceVisible = liveProgressVisible || pipelineActive || jobPolling;
  const surfacePrecedence = recoverySurfacePrecedence(notice, progressSurfaceVisible);
  const selectedJourneyStage = journeyStageForGenerate(opportunityId) ?? null;
  const approvalBlocked = review ? isApprovalBlocked(review) : false;
  const approvalReady = canApproveAndBuild({
    editable,
    confirmed: frameworkConfirmed,
    humanConfirmed,
    blocked: approvalBlocked,
  });
  const workflowBusy = Boolean(busy || downloadingFormat || progressSurfaceVisible);
  const workflowPrimaryDisabled = Boolean(
    workflowBusy || (notice && surfacePrecedence.showRecovery),
  );
  const chapterAttentionIds = new Set(
    (review?.attention_signals ?? [])
      .filter((signal) => signal.severity !== "info")
      .map((signal) => signal.chapter_id)
      .filter((chapterId): chapterId is string => Boolean(chapterId)),
  );

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

        <WorkflowActionBar
          backHref={pipelineHref("/upload", opportunityId)}
          backLabel="Back to intake"
          contextLabel="Current step"
          context={
            <>
              <strong>
                {pipelineActive
                  ? "Building presentation"
                  : jobPolling
                    ? "Building customer story"
                    : frameworkConfirmed
                      ? "Customer story approved"
                      : "Customer story review"}
              </strong>
              <JourneyStageChoice stage={selectedJourneyStage} />
            </>
          }
        >
          {frameworkVersion && !frameworkConfirmed && editable ? (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={workflowBusy || !dirty}
              onClick={() => void handleSave()}
            >
              {busy && dirty ? "Saving..." : "Save changes"}
            </button>
          ) : null}
          {!frameworkVersion ? (
            <button
              type="button"
              className="btn btn-primary"
              disabled={workflowPrimaryDisabled || frameworkLoading || (transcriptCount ?? 0) === 0}
              onClick={() => void handleGenerate()}
            >
              {jobPolling ? "Building customer story..." : "Generate customer story"}
            </button>
          ) : frameworkConfirmed ? (
            <button
              type="button"
              className="btn btn-primary"
              disabled={workflowPrimaryDisabled}
              onClick={() => void handleBuildConfirmedFramework()}
            >
              {pipelineActive ? "Building presentation..." : "Build presentation"}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              data-testid="framework-top-approve-button"
              disabled={workflowPrimaryDisabled || !approvalReady}
              onClick={() => void handleApprove()}
            >
              Approve &amp; build presentation
            </button>
          )}
        </WorkflowActionBar>

        <AppPageHeader
          kicker="Customer story review"
          title="Review the customer story"
          lead="Start with the summary, resolve anything that needs attention, then open individual chapters when you need more detail."
        />

        <div className="framework-review-main" id="framework-review-content">
            {notice && surfacePrecedence.showRecovery ? (
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
            {info && surfacePrecedence.showSecondary ? (
              <div className="upload-banner upload-banner-success">{info}</div>
            ) : null}

            {frameworkLoading && !frameworkVersion ? (
              <section className="upload-panel pipeline-panel-loading">
                <p className="upload-hint" data-testid="framework-loading">
                  Loading customer story…
                </p>
              </section>
            ) : null}

            {surfacePrecedence.showProgress ? (
              liveProgressVisible && liveProgressView ? (
                <LiveGenerationProgress view={liveProgressView} />
              ) : pipelineActive ? (
                <section className="upload-panel pipeline-panel-loading">
                  <p className="upload-hint" data-testid="pipeline-job-progress">
                    Starting the presentation pipeline…
                  </p>
                </section>
              ) : jobPolling ? (
                <section className="upload-panel pipeline-panel-loading">
                  <p className="upload-hint" data-testid="pipeline-job-progress">
                    {info ?? "Framework generation is running…"}
                    {jobStage ? ` · ${jobStageLabel(jobStage)}` : ""}
                  </p>
                </section>
              ) : null
            ) : null}

            {!frameworkLoading && !frameworkVersion && isAuthenticated && !notice ? (
              <section className="upload-panel pipeline-empty-panel">
                <header className="upload-panel-header">
                  <div>
                    <h2>Generate the customer story</h2>
                    <p>
                      Create the {EXPECTED_CHAPTER_COUNT}-chapter customer report from the
                      transcripts attached to this opportunity.
                    </p>
                  </div>
                </header>
                <div className="pipeline-empty-body">
                  <div className="pipeline-empty-hero">
                    <div className="pipeline-empty-visual" aria-hidden="true">
                      <div className="pipeline-empty-icon">{EXPECTED_CHAPTER_COUNT}</div>
                      <span className="pipeline-empty-icon-label">chapters</span>
                    </div>
                    {(transcriptCount ?? 0) === 0 ? (
                      <>
                        <div className="pipeline-empty-copy">
                          <div className="pipeline-empty-status pipeline-empty-status-wait">
                            <span className="pipeline-empty-dot pipeline-empty-dot-wait" />
                            Transcripts needed
                          </div>
                          <p>
                            Upload at least one discovery transcript, then generate the customer
                            story from this page.
                          </p>
                          <ol className="pipeline-empty-steps">
                            <li>Upload a transcript</li>
                            <li>Generate the draft</li>
                            <li>Review and approve</li>
                          </ol>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="pipeline-empty-copy">
                          <div className="pipeline-empty-status pipeline-empty-status-ready">
                            <span className="pipeline-empty-dot pipeline-empty-dot-ready" />
                            {transcriptCount} transcript{transcriptCount === 1 ? "" : "s"} ready
                          </div>
                          <p>
                            Generation usually takes a minute. Review the summary first, then
                            inspect chapters and cited sources before you approve.
                          </p>
                          <ol className="pipeline-empty-steps">
                            <li>Generate the draft</li>
                            <li>Review the summary</li>
                            <li>Inspect chapters and sources</li>
                          </ol>
                        </div>
                      </>
                    )}
                  </div>
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
                      showActions={false}
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
                        </>
                      ) : null}
                    </div>
                  )}

                  <div className="framework-export-panel" data-testid="framework-export-panel">
                    <div>
                      <strong>Download the customer report</strong>
                      <p>
                        Export the complete 14-chapter report as Word or PDF. Draft versions are
                        labeled until you approve. Word is available in English and German.
                      </p>
                    </div>
                    <div className="framework-toolbar-actions">
                      <button
                        type="button"
                        className="btn btn-secondary"
                        data-testid="framework-download-word"
                        disabled={busy || downloadingFormat !== null}
                        onClick={() => void handleDownloadFramework("docx", "en")}
                      >
                        {downloadingFormat === "docx" && downloadLanguage === "en"
                          ? "Downloading…"
                          : "Word (English)"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        data-testid="framework-download-word-de"
                        disabled={busy || downloadingFormat !== null}
                        onClick={() => void handleDownloadFramework("docx", "de")}
                      >
                        {downloadingFormat === "docx" && downloadLanguage === "de"
                          ? "Downloading…"
                          : "Word (Deutsch)"}
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

                <section className="framework-chapter-browser" id="framework-chapters">
                  <header className="framework-chapter-browser-header">
                    <div>
                      <p className="journey-start-kicker">Detailed review</p>
                      <h2>Chapters</h2>
                      <p>Open one chapter at a time to review its content and cited sources.</p>
                    </div>
                    <span className="framework-chapter-count">
                      {frameworkJson.chapters.length} chapters
                    </span>
                  </header>

                  <ol className="framework-chapter-list">
                    {chapterNav.map((item) => {
                      const chapter = frameworkJson.chapters[item.index];
                      if (!chapter) {
                        return null;
                      }
                      const isOpen = activeChapterId === item.chapterId;
                      const previousChapter = chapterNav[item.index - 1];
                      const nextChapter = chapterNav[item.index + 1];
                      const panelId = `framework-chapter-panel-${item.chapterId}`;
                      const buttonId = `framework-chapter-button-${item.chapterId}`;
                      return (
                        <li
                          key={item.chapterId}
                          id={`framework-chapter-${item.chapterId}`}
                          className={`framework-chapter-list-item${isOpen ? " is-open" : ""}`}
                        >
                          <button
                            id={buttonId}
                            type="button"
                            className="framework-chapter-list-button"
                            aria-expanded={isOpen}
                            aria-controls={panelId}
                            onClick={() =>
                              isOpen ? closeChapter(item.chapterId) : openChapter(item.chapterId)
                            }
                          >
                            <span className="framework-chapter-list-number">
                              Chapter {item.chapterId}
                            </span>
                            <span className="framework-chapter-list-title">{item.title}</span>
                            <span className="framework-chapter-list-meta">
                              {item.refCount} cited source{item.refCount === 1 ? "" : "s"}
                              {chapterAttentionIds.has(item.chapterId) ? (
                                <span className="framework-chapter-attention">Needs attention</span>
                              ) : null}
                            </span>
                            <span className="framework-chapter-list-action">
                              {isOpen ? "Hide details" : "Open details"}
                            </span>
                          </button>

                          {isOpen ? (
                            <div
                              id={panelId}
                              className="framework-chapter-detail"
                              role="region"
                              aria-labelledby={buttonId}
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
                                    updateChapter(frameworkJson, item.index, nextChapter),
                                  );
                                }}
                              />
                              <nav
                                className="framework-chapter-pagination"
                                aria-label="Chapter navigation"
                              >
                                {previousChapter ? (
                                  <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => openChapter(previousChapter.chapterId, true)}
                                  >
                                    Previous chapter
                                  </button>
                                ) : <span />}
                                {nextChapter ? (
                                  <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => openChapter(nextChapter.chapterId, true)}
                                  >
                                    Next chapter
                                  </button>
                                ) : null}
                              </nav>
                            </div>
                          ) : null}
                        </li>
                      );
                    })}
                  </ol>
                </section>
              </>
            ) : null}
        </div>
      </div>
    </div>
  );
}

