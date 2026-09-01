"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import { PipelineStepper } from "@/components/PipelineStepper";
import { SiteHeader } from "@/components/SiteHeader";
import { loadActiveOpportunity, pipelineHref } from "@/lib/pipelineContext";

interface PipelineContextMissingProps {
  title: string;
  detail: string;
}

/** Shown when a pipeline step is opened without ?opportunityId= (expected after upload). */
export function PipelineContextMissing({ title, detail }: PipelineContextMissingProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [restoring, setRestoring] = useState(true);

  useEffect(() => {
    const stored = loadActiveOpportunity();
    if (stored?.id) {
      router.replace(pipelineHref(pathname, stored.id));
      return;
    }
    setRestoring(false);
  }, [pathname, router]);

  return (
    <div className="app-workspace">
      <SiteHeader />
      <div className="app-shell app-workspace-body">
        <PipelineStepper
          currentStep={
            pathname.startsWith("/framework-review")
              ? 2
              : pathname.startsWith("/plan-preview")
                ? 3
                : pathname.startsWith("/deck-center")
                  ? 4
                  : 1
          }
        />
        <AppPageHeader kicker="Pipeline" title={title} lead={detail} />
        <div className="upload-panel pipeline-empty-panel">
          <div className="pipeline-empty-body">
            <span className="pipeline-empty-icon" aria-hidden="true">
              1→2
            </span>
            {restoring ? (
              <p className="upload-hint">Restoring your opportunity…</p>
            ) : (
              <>
                <p className="upload-hint">
                  This step is part of the pipeline after you create an opportunity on the upload
                  page.
                </p>
                <p>
                  Start there, then use <strong>Review framework</strong> once an opportunity is
                  active.
                </p>
                <Link href="/upload" className="btn btn-primary">
                  Go to upload
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
