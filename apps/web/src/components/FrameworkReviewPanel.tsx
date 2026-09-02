"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { useAuth } from "@/components/AuthProvider";
import { FrameworkChapterView } from "@/components/FrameworkChapterView";
import { FrameworkReviewSummary } from "@/components/FrameworkReviewSummary";
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
import { customerStatusLabel } from "@/lib/frameworkLabels";
import {
  canApproveAndBuild,
  isApprovalBlocked,
  reviewPayloadFromUnknown,
  type FrameworkReviewPayload,
} from "@/lib/frameworkReview";
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
  const [hoveredChapterId, setHoveredChapterId] = useState<string | null>(null);
  const [downloadingFormat, setDownloadingFormat] = useState<"docx" | "pdf" | null>(null);
  const chapterNavItemRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
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
      waitForJob: (jobId) => waitForJob(token, jobId),
      generatePresentationPlan: (frameworkVersionId, autoContinue) =>
        generatePresentationPlan(token, opportunityId, frameworkVersionId, autoContinue),
      getLatestPresentationPlan: () => getLatestPresentationPlan(token, opportunityId),
      getPresentationPlan: (presentationPlanId) =>
        getPresentationPlan(token, presentationPlanId),
      getPresentation: (presentationId) => getPresentation(token, presentationId),
    }),
    [opportunityId],
  );

  const reportPresentationProgress = useCallback((progress: PresentationPipelineProgress) => {
    setRecoveryTarget("presentation-pipeline");
    setNotice(
      runningRecoveryNotice(
        progress.phase === "planning" ? "plan" : "deck",
        progress.jobId,
      ),
    );
    if (progress.phase === "planning") {
      setInfo(
        progress.state === "completed"
          ? "Presentation plan completed. Starting presentation generation…"
          : progress.reused
            ? "Resuming presentation planning…"
            : "Presentation planning is running…",
      );
      return;
    }
    setInfo(
      progress.state === "completed"
        ? "Presentation is ready. Opening the deck…"
        : progress.reused
          ? "Resuming presentation generation…"
          : "Presentation generation is running…",
    );
  }, []);

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
    setRetryJobId(null);
    setRecoveryTarget("presentation-pipeline");
    const reconnectAction =
      recovered.action?.kind === "RECONNECT" || recovered.action?.kind === "KEEP_CHECKING"
        ? recovered.action
        : null;
    setNotice({
      ...recovered,
      action: reconnectAction ??
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
          onProgress: reportPresentationProgress,
        });
        if (recovery.state === "completed") {
          setNotice(null);
          openPresentationResult(recovery.result);
        }
      } catch (error) {
        reportPresentationFailure(error);
      } finally {
        presentationPipelineRunningRef.current = false;
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
      setInfo(`Updating chapter ${chapterId}…`);
      await waitForJob(accessToken, queued.job_id, FRAMEWORK_JOB_TIMEOUT_MS);
      await loadFramework();
      setInfo(`Chapter ${chapterId} was updated. Other chapters were left unchanged.`);
    } catch (regenerateError) {
      setNotice(recoveryNoticeFromError(regenerateError, "framework"));
    } finally {
      setRegeneratingChapterId(null);
      setBusy(false);
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
      setBusy(false);
    }
  }

  async function handleApprove() {
    await handleApproveAndBuild(false);
  }

  async function handleBuildConfirmedFramework() {
    await handleApproveAndBuild(true);
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
                  ? "This customer story is approved. Build the presentation here, or optionally inspect the slide structure."
                  : "Approve only after you have reviewed the summary and any warnings."}
              </p>
              <Link href={pipelineHref("/upload", opportunityId)} className="btn btn-secondary btn-block">
                Back to upload
              </Link>
              {frameworkConfirmed ? (
                <Link
                  href={pipelineHref("/plan-preview", opportunityId)}
                  className="btn btn-secondary btn-block"
                >
                  View presentation structure
                </Link>
              ) : (
                <a href="#framework-chapters" className="btn btn-secondary btn-block">
                  Review all 14 chapters
                </a>
              )}
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
                  Loading customer story…
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

                {frameworkConfirmed && !notice ? (
                  <div className="upload-banner upload-banner-info">
                    <div>
                      <strong>Framework confirmed</strong>
                      <p>
                        This version is locked. Fields, source references, and chapter regenerate
                        stay read-only so Stage B can only use the confirmed object. Presentation
                        building can continue here without opening Plan Preview first.
                      </p>
                    </div>
                    <div className="upload-banner-actions">
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={busy || downloadingFormat !== null}
                        onClick={() => void handleBuildConfirmedFramework()}
                      >
                        Build presentation
                      </button>
                    </div>
                  </div>
                ) : null}

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

