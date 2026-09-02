"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { useAuth } from "@/components/AuthProvider";
import { LiveGenerationProgress } from "@/components/LiveGenerationProgress";
import { PipelineStepper } from "@/components/PipelineStepper";
import { RecoveryBanner } from "@/components/RecoveryBanner";
import { SiteHeader } from "@/components/SiteHeader";
import {
  ApiRequestError,
  FRAMEWORK_JOB_TIMEOUT_MS,
  generatePresentationPlan,
  getActiveJob,
  getJob,
  getLatestFramework,
  getLatestPresentationPlan,
  retryJob,
  waitForJob,
} from "@/lib/api";
import type { JobResponse } from "@/lib/api";
import { isMissingFrameworkError, isMissingPresentationPlanError } from "@/lib/apiErrors";
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
import { startPipelineParallelLoad } from "@/lib/pipelineParallelLoad";
import { pipelineHref } from "@/lib/pipelineContext";
import { extractSlidePreviewRows, formatLayoutLabel } from "@/lib/planPreview";
import type { PresentationPlanResponse } from "@/lib/planTypes";
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

interface PlanPreviewPanelProps {
  opportunityId: string;
}

export function PlanPreviewPanel({ opportunityId }: PlanPreviewPanelProps) {
  const { accessToken, isAuthenticated, loading, session } = useAuth();
  const [frameworkConfirmed, setFrameworkConfirmed] = useState<boolean | null>(null);
  const [frameworkVersionId, setFrameworkVersionId] = useState<string | null>(null);
  const [plan, setPlan] = useState<PresentationPlanResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [planLoading, setPlanLoading] = useState(true);
  const [jobPolling, setJobPolling] = useState(false);
  const [jobStage, setJobStage] = useState<string | null>(null);
  const [jobSnapshot, setJobSnapshot] = useState<JobProgressSnapshot | null>(null);
  const [notice, setNotice] = useState<RecoveryNotice | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [retryJobId, setRetryJobId] = useState<string | null>(null);

  const slideRows = useMemo(() => {
    if (!plan) {
      return [];
    }
    return extractSlidePreviewRows(plan.plan_json);
  }, [plan]);

  const trackJob = useCallback((job: JobResponse) => {
    setJobSnapshot(snapshotFromJob(job));
  }, []);

  const progressView = useMemo(
    () =>
      buildJobProgressView({
        snapshot: jobSnapshot,
        // Only the plan being generated from counts; a stale plan must not be quoted.
        plannedSlideCount:
          plan && jobSnapshot?.jobType === "presentation_generation" ? slideRows.length : null,
      }),
    [jobSnapshot, plan, slideRows.length],
  );

  const loadFrameworkStatus = useCallback(async () => {
    if (!accessToken) {
      return null;
    }
    try {
      const latest = await getLatestFramework(accessToken, opportunityId);
      return { confirmed: latest.status === "confirmed", frameworkVersionId: latest.id };
    } catch (statusError) {
      if (!isMissingFrameworkError(statusError)) {
        throw statusError;
      }
      return { confirmed: false, frameworkVersionId: null };
    }
  }, [accessToken, opportunityId]);

  const applyLatestPlan = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const latest = await getLatestPresentationPlan(accessToken, opportunityId);
      setPlan(latest);
    } catch (loadError) {
      setPlan(null);
      if (!isMissingPresentationPlanError(loadError)) {
        throw loadError;
      }
    }
  }, [accessToken, opportunityId]);

  const loadPlan = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      await applyLatestPlan();
    } catch (loadError) {
      setNotice(recoveryNoticeFromError(loadError, "plan"));
    } finally {
      setBusy(false);
    }
  }, [accessToken, applyLatestPlan]);

  useEffect(() => {
    if (loading || !accessToken) {
      return;
    }
    const token = accessToken;
    let cancelled = false;

    void loadFrameworkStatus()
      .then((frameworkStatus) => {
        if (!cancelled) {
          setFrameworkConfirmed(frameworkStatus?.confirmed ?? false);
          setFrameworkVersionId(frameworkStatus?.frameworkVersionId ?? null);
        }
      })
      .catch((statusError) => {
        if (!cancelled) {
          setNotice(recoveryNoticeFromError(statusError, "plan"));
        }
      });

    setPlanLoading(true);
    setJobPolling(false);
    setJobStage(null);
    setJobSnapshot(null);
    setNotice(null);
    setInfo(null);
    setRetryJobId(null);

    const cancel = startPipelineParallelLoad(
      "plan",
      {
        onContentLoaded: () => {},
        onContentMissing: () => {
          setPlan(null);
        },
        onContentLoadFinished: () => {
          setPlanLoading(false);
        },
        onContentLoadError: (message) => {
          setNotice(recoveryNoticeFromError(new Error(message), "plan"));
        },
        onJobPollingStart: (message, stage, jobId) => {
          setJobPolling(true);
          setInfo(message);
          setJobStage(stage);
          setNotice(runningRecoveryNotice("plan", jobId));
        },
        onJobStageUpdate: (stage) => {
          setJobStage(stage);
        },
        onJobSnapshot: setJobSnapshot,
        onJobPollingFinished: () => {
          setJobPolling(false);
          setInfo(null);
          setJobStage(null);
          setJobSnapshot(null);
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
              "plan",
            ),
          );
          setRetryJobId(failedJobId);
        },
      },
      {
        loadContent: async () => {
          const latest = await getLatestPresentationPlan(token, opportunityId);
          if (!cancelled) {
            setPlan(latest);
          }
        },
        isMissingError: isMissingPresentationPlanError,
        getActiveJob: () => getActiveJob(token, opportunityId, stageGroupForPage("plan")),
        getJob: (jobId) => getJob(token, jobId),
      },
    );

    return () => {
      cancelled = true;
      cancel();
    };
  }, [accessToken, loadFrameworkStatus, loading, opportunityId]);

  async function handleGeneratePlan() {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setNotice(null);
    setInfo(null);
    setRetryJobId(null);
    try {
      const generated = await generatePresentationPlan(
        accessToken,
        opportunityId,
        frameworkVersionId ?? undefined,
      );
      setInfo(generationProgressMessage("plan", Boolean(generated.is_existing_job)));
      setNotice(runningRecoveryNotice("plan", generated.job_id));
      setJobPolling(true);
      await waitForJob(accessToken, generated.job_id, {
        timeoutMs: FRAMEWORK_JOB_TIMEOUT_MS,
        onProgress: trackJob,
      });
      setJobPolling(false);
      setJobSnapshot(null);
      setNotice(null);
      await loadPlan();
      setInfo("Presentation plan ready. Review order, purpose, and layout below.");
    } catch (generateError) {
      setInfo(null);
      setNotice(recoveryNoticeFromError(generateError, "plan"));
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
    setJobSnapshot(null);
    setBusy(true);
    setNotice(retryingRecoveryNotice("plan", retryJobId));
    setInfo("Retrying generation from the last failed stage...");
    try {
      const queued = await retryJob(accessToken, retryJobId);
      setRetryJobId(null);
      setJobPolling(true);
      await waitForJob(accessToken, queued.job_id, {
        timeoutMs: FRAMEWORK_JOB_TIMEOUT_MS,
        onProgress: trackJob,
      });
      setJobSnapshot(null);
      setNotice(null);
      await loadPlan();
    } catch (retryError) {
      setInfo(null);
      setNotice(recoveryNoticeFromError(retryError, "plan"));
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
    setNotice(runningRecoveryNotice("plan"));
    try {
      const frameworkStatus = await loadFrameworkStatus();
      setFrameworkConfirmed(frameworkStatus?.confirmed ?? false);
      setFrameworkVersionId(frameworkStatus?.frameworkVersionId ?? null);
      const job = await getActiveJob(accessToken, opportunityId, stageGroupForPage("plan"));
      const decision = inspectActiveJob(job, "plan");
      if (decision.action === "failed") {
        setRetryJobId(decision.retryable ? decision.jobId : null);
        setNotice(jobFailureRecoveryNotice(decision.error, "plan", decision.jobId));
        return;
      }
      if (decision.action === "monitor") {
        setNotice(runningRecoveryNotice("plan", decision.jobId));
        setJobPolling(true);
        await waitForJob(accessToken, decision.jobId, {
          timeoutMs: FRAMEWORK_JOB_TIMEOUT_MS,
          onProgress: trackJob,
        });
        setJobSnapshot(null);
      }
      await applyLatestPlan();
      setNotice(null);
    } catch (reconnectError) {
      setNotice(recoveryNoticeFromError(reconnectError, "plan"));
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

  const activeNotice =
    notice ?? (frameworkConfirmed === false ? inputRequiredRecoveryNotice("plan") : null);

  function handleRecoveryAction() {
    if (activeNotice?.action?.kind === "RETRY") {
      void handleRetry();
      return;
    }
    if (
      activeNotice?.action?.kind === "RECONNECT" ||
      activeNotice?.action?.kind === "KEEP_CHECKING"
    ) {
      void handleReconnect();
    }
  }

  const progressSurfaceVisible = Boolean(jobPolling || progressView?.failed);
  const surfacePrecedence = recoverySurfacePrecedence(activeNotice, progressSurfaceVisible);

  return (
    <div className="app-workspace">
      <SiteHeader signedInEmail={session?.user.email} opportunityId={opportunityId} />

      <div className="app-shell app-workspace-body">
        {!loading && isAuthenticated ? <span data-testid="auth-ready" hidden /> : null}

        {!loading && !isAuthenticated ? (
          <div className="upload-banner upload-banner-info">
            <div>
              <strong>Authentication required</strong>
              <p>Sign in to preview the presentation plan for this opportunity.</p>
            </div>
            <div className="upload-banner-actions">
              <Link href="/login" className="btn btn-primary">
                Sign in
              </Link>
            </div>
          </div>
        ) : null}

        <PipelineStepper
          currentStep={3}
          opportunityId={opportunityId}
          frameworkReady={frameworkConfirmed !== false}
          frameworkConfirmed={Boolean(frameworkConfirmed)}
          planReady={Boolean(plan)}
        />
        <AppPageHeader
          kicker="Step 3 of 4"
          title="Presentation plan preview"
          lead="Review the planned slide sequence - order, purpose, and layout - before committing to full deck generation."
        />

        <div className="upload-layout">
          <aside className="upload-sidebar">
            <div className="upload-meta-card">
              <h3>Active opportunity</h3>
              <p className="upload-meta-empty">Confirm the slide order before generating the deck.</p>
              <Link
                href={`/framework-review?opportunityId=${opportunityId}`}
                className="btn btn-secondary btn-block"
              >
                Back to framework
              </Link>
              {plan ? (
                <Link
                  href={pipelineHref("/deck-center", opportunityId)}
                  className="btn btn-primary btn-block"
                >
                  Open presentation
                </Link>
              ) : null}
            </div>
          </aside>

          <div className="upload-main">
        {activeNotice && surfacePrecedence.showRecovery ? (
          <RecoveryBanner
            notice={
              recoveryActionHref(activeNotice, opportunityId)
                ? {
                    ...activeNotice,
                    action: {
                      ...activeNotice.action!,
                      href: recoveryActionHref(activeNotice, opportunityId),
                    },
                  }
                : activeNotice
            }
            busy={busy}
            onAction={handleRecoveryAction}
          />
        ) : null}
        {info && surfacePrecedence.showSecondary ? (
          <div className="upload-banner upload-banner-success">{info}</div>
        ) : null}

        {planLoading && !plan ? (
          <section className="upload-panel pipeline-panel-loading">
            <p className="upload-hint" data-testid="plan-loading">
              Loading presentation plan…
            </p>
          </section>
        ) : null}

        {surfacePrecedence.showProgress ? (
          progressView && (jobPolling || progressView.failed) ? (
            <LiveGenerationProgress view={progressView} />
          ) : jobPolling ? (
            <section className="upload-panel pipeline-panel-loading">
              <p className="upload-hint" data-testid="pipeline-job-progress">
                {info ?? "Presentation planning is running…"}
                {jobStage ? ` · ${jobStageLabel(jobStage)}` : ""}
              </p>
            </section>
          ) : null
        ) : null}

        {!planLoading && !plan && frameworkConfirmed && isAuthenticated && !activeNotice ? (
          <section className="upload-panel pipeline-empty-panel">
            <header className="upload-panel-header">
              <div>
                <h2>Generate the presentation plan</h2>
                <p>
                  After the customer story is approved, generate the slide plan to review order
                  and purpose before building the presentation.
                </p>
              </div>
            </header>
            <div className="pipeline-empty-body">
              <p>No presentation plan exists yet for this opportunity.</p>
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={() => void handleGeneratePlan()}
              >
                Generate plan
              </button>
            </div>
          </section>
        ) : null}

        {plan ? (
          <section className="upload-panel">
            <header className="upload-panel-header">
              <div>
                <h2>{plan.plan_json.title}</h2>
                <p className="upload-hint">
                  {slideRows.length} planned slide{slideRows.length === 1 ? "" : "s"}
                </p>
              </div>
            </header>

            <div className="plan-table-wrap">
              <table className="plan-table" data-testid="plan-slide-table">
                <thead>
                  <tr>
                    <th scope="col">Order</th>
                    <th scope="col">Purpose</th>
                    <th scope="col">Layout</th>
                  </tr>
                </thead>
                <tbody>
                  {slideRows.map((row) => (
                    <tr key={`${row.order}-${row.layoutId}`}>
                      <td>{row.order}</td>
                      <td>{row.purpose}</td>
                      <td>{formatLayoutLabel(row.layoutId)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <details className="framework-details-disclosure">
              <summary>Details</summary>
              <p className="upload-hint">
                {slideRows.map((row) => `Slide ${row.order}: ${row.layoutId}`).join(" · ")}
              </p>
            </details>

            <p className="upload-hint plan-next-step">
              <strong>Plan complete.</strong> Continue to the presentation to preview slides and
              download the PowerPoint.
            </p>
          </section>
        ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
