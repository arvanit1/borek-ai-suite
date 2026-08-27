"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { PipelineStepper } from "@/components/PipelineStepper";
import { SiteHeader } from "@/components/SiteHeader";
import {
  generatePresentationPlan,
  getLatestFramework,
  getLatestPresentationPlan,
} from "@/lib/api";
import { isMissingPresentationPlanError } from "@/lib/apiErrors";
import { extractSlidePreviewRows, formatLayoutLabel } from "@/lib/planPreview";
import type { PresentationPlanResponse } from "@/lib/planTypes";

interface PlanPreviewPanelProps {
  opportunityId: string;
}

export function PlanPreviewPanel({ opportunityId }: PlanPreviewPanelProps) {
  const { accessToken, isAuthenticated, loading, session } = useAuth();
  const [frameworkConfirmed, setFrameworkConfirmed] = useState<boolean | null>(null);
  const [frameworkVersionId, setFrameworkVersionId] = useState<string | null>(null);
  const [plan, setPlan] = useState<PresentationPlanResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const slideRows = useMemo(() => {
    if (!plan) {
      return [];
    }
    return extractSlidePreviewRows(plan.plan_json);
  }, [plan]);

  const loadFrameworkStatus = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const latest = await getLatestFramework(accessToken, opportunityId);
      setFrameworkConfirmed(latest.status === "confirmed");
      setFrameworkVersionId(latest.id);
    } catch {
      setFrameworkConfirmed(false);
      setFrameworkVersionId(null);
    }
  }, [accessToken, opportunityId]);

  const loadPlan = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const latest = await getLatestPresentationPlan(accessToken, opportunityId);
      setPlan(latest);
    } catch (loadError) {
      setPlan(null);
      if (!isMissingPresentationPlanError(loadError)) {
        const message =
          loadError instanceof Error ? loadError.message : "Could not load presentation plan.";
        setError(message);
      }
    } finally {
      setBusy(false);
    }
  }, [accessToken, opportunityId]);

  useEffect(() => {
    if (!loading && accessToken) {
      void loadFrameworkStatus();
      void loadPlan();
    }
  }, [accessToken, loading, loadFrameworkStatus, loadPlan]);

  async function handleGeneratePlan() {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await generatePresentationPlan(
        accessToken,
        opportunityId,
        frameworkVersionId ?? undefined,
      );
      await loadPlan();
      setInfo("Presentation plan ready. Review order, purpose, and layout below.");
    } catch (generateError) {
      setError(
        generateError instanceof Error ? generateError.message : "Plan generation failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="upload-page">
      <SiteHeader signedInEmail={session?.user.email} />

      <div className="upload-hero">
        <div className="app-shell upload-hero-inner">

          <h1>Presentation plan preview</h1>
          <p className="upload-lead">
            Review the planned slide sequence — order, purpose, and layout — before committing to
            full deck generation.
          </p>
        </div>
      </div>

      <div className="app-shell upload-body">
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

        <div className="upload-layout">
          <aside className="upload-sidebar">
            <PipelineStepper
              currentStep={3}
              frameworkReady={frameworkConfirmed !== false}
              frameworkConfirmed={Boolean(frameworkConfirmed)}
              planReady={Boolean(plan)}
            />
            <div className="upload-meta-card">
              <h3>Active opportunity</h3>
              <code className="upload-meta-id">{opportunityId}</code>
              <Link
                href={`/framework-review?opportunityId=${opportunityId}`}
                className="btn btn-secondary btn-block"
              >
                Back to framework
              </Link>
              {plan ? (
                <Link
                  href={`/deck-center?opportunityId=${opportunityId}`}
                  className="btn btn-primary btn-block"
                >
                  Open deck center
                </Link>
              ) : null}
            </div>
          </aside>

          <div className="upload-main">
        {frameworkConfirmed === false ? (
          <div className="upload-banner upload-banner-info">
            <div>
              <strong>Confirmed framework required</strong>
              <p>
                Presentation planning starts only after the framework is confirmed. Review and
                confirm the framework first.
              </p>
            </div>
            <div className="upload-banner-actions">
              <Link
                href={`/framework-review?opportunityId=${opportunityId}`}
                className="btn btn-primary"
              >
                Review framework
              </Link>
            </div>
          </div>
        ) : null}

        {error ? <div className="alert alert-error">{error}</div> : null}
        {info ? <div className="upload-banner upload-banner-success">{info}</div> : null}

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
                      <td>
                        <code>{row.layoutId}</code>
                        <span className="plan-layout-label">{formatLayoutLabel(row.layoutId)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="upload-hint plan-next-step">
              <strong>Step 3 complete.</strong> When you are satisfied with the planned sequence,
              continue to the deck center to generate slide previews and download the presentation.
            </p>
          </section>
        ) : frameworkConfirmed && !busy && isAuthenticated ? (
          <section className="upload-panel pipeline-empty-panel">
            <header className="upload-panel-header">
              <div>
                <h2>Generate the presentation plan</h2>
                <p>
                  After the framework is confirmed, generate the slide plan to review order,
                  purpose, and layout before full deck generation.
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
          </div>
        </div>
      </div>
    </div>
  );
}
