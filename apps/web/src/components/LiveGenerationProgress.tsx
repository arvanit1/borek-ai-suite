"use client";

import React, { useEffect, useState } from "react";

import {
  elapsedMsSince,
  formatElapsedLabel,
  type JobProgressStepState,
  type JobProgressView,
} from "@/lib/jobProgress";

interface LiveGenerationProgressProps {
  view: JobProgressView;
  /** Injected in tests; the component uses the wall clock by default. */
  nowMs?: number;
}

const STEP_MARKS: Record<JobProgressStepState, string> = {
  complete: "✓",
  current: "●",
  upcoming: "○",
  failed: "×",
};

const STEP_STATUS_TEXT: Record<JobProgressStepState, string> = {
  complete: "Done",
  current: "In progress",
  upcoming: "Waiting",
  failed: "Stopped",
};

export function LiveGenerationProgress({ view, nowMs }: LiveGenerationProgressProps) {
  const settled = view.status === "COMPLETED" || view.status === "FAILED";
  const [tick, setTick] = useState(() => nowMs ?? Date.now());

  useEffect(() => {
    if (nowMs !== undefined || settled || !view.elapsedFrom) {
      return;
    }
    const timer = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [nowMs, settled, view.elapsedFrom]);

  const elapsed = elapsedMsSince(
    { startedAt: view.elapsedFrom, createdAt: null, completedAt: view.elapsedTo },
    nowMs ?? tick,
  );

  return (
    <section
      className="upload-panel live-progress"
      data-testid="live-generation-progress"
      data-phase={view.phase}
      data-status={view.status}
      data-job-type={view.jobType}
    >
      <header className="live-progress-header">
        <div>
          <h2 className="live-progress-title">{view.title}</h2>
          <p
            className={`live-progress-headline${view.failed ? " live-progress-headline-failed" : ""}`}
            role="status"
            aria-live="polite"
            data-testid="live-progress-headline"
          >
            {view.headline}
          </p>
        </div>
        {elapsed !== null ? (
          <span className="live-progress-elapsed" data-testid="live-progress-elapsed">
            {formatElapsedLabel(elapsed)}
          </span>
        ) : null}
      </header>

      <ol className="live-progress-steps">
        {view.steps.map((step) => (
          <li
            key={step.id}
            className="live-progress-step"
            data-step={step.id}
            data-state={step.state}
            aria-current={step.state === "current" ? "step" : undefined}
          >
            <span className="live-progress-mark" aria-hidden="true">
              {STEP_MARKS[step.state]}
            </span>
            <span className="live-progress-step-label">{step.label}</span>
            <span className="live-progress-step-status">{STEP_STATUS_TEXT[step.state]}</span>
          </li>
        ))}
      </ol>

      {view.detail ? (
        <p className="upload-hint live-progress-detail" data-testid="live-progress-detail">
          {view.detail}
        </p>
      ) : null}
    </section>
  );
}
