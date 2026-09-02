"use client";

import Link from "next/link";
import React from "react";

import type { RecoveryNotice } from "@/lib/recoveryUx";

interface RecoveryBannerProps {
  notice: RecoveryNotice;
  busy?: boolean;
  onAction?: () => void;
}

const STATUS_CATEGORIES = new Set(["CONNECTION_LOST", "STILL_RUNNING", "RETRYING"]);

export function RecoveryBanner({ notice, busy = false, onAction }: RecoveryBannerProps) {
  const status = STATUS_CATEGORIES.has(notice.category);
  const technical = notice.technical;
  const hasTechnical = Boolean(
    technical?.code || technical?.stage || technical?.jobId || technical?.message,
  );

  return (
    <div
      className={`alert recovery-banner ${status ? "alert-info" : "alert-error"}`}
      role={status ? "status" : "alert"}
      aria-live={status ? "polite" : "assertive"}
      data-testid="recovery-banner"
      data-recovery-category={notice.category}
    >
      <div className="recovery-banner-copy">
        <strong>{notice.title}</strong>
        <p>{notice.message}</p>
        {hasTechnical ? (
          <details className="recovery-details">
            <summary>Details for support</summary>
            {technical?.code ? <p>Error code: {technical.code}</p> : null}
            {technical?.stage ? <p>Stage: {technical.stage}</p> : null}
            {technical?.jobId ? <p>Job reference: {technical.jobId}</p> : null}
            {technical?.message ? <p>Technical message: {technical.message}</p> : null}
          </details>
        ) : null}
      </div>
      {notice.action ? (
        notice.action.href ? (
          <Link
            href={notice.action.href}
            className="btn btn-secondary"
            data-testid="recovery-action"
          >
            {notice.action.label}
          </Link>
        ) : (
          <button
            type="button"
            className="btn btn-secondary"
            disabled={busy || !onAction}
            onClick={onAction}
            data-testid="recovery-action"
          >
            {notice.action.label}
          </button>
        )
      ) : null}
    </div>
  );
}
