import Link from "next/link";

import { AppPageHeader } from "@/components/AppPageHeader";
import { SiteHeader } from "@/components/SiteHeader";

interface PipelineContextMissingProps {
  title: string;
  detail: string;
}

/** Shown when a pipeline step is opened without ?opportunityId= (expected after upload). */
export function PipelineContextMissing({ title, detail }: PipelineContextMissingProps) {
  return (
    <div className="app-workspace">
      <SiteHeader />
      <div className="app-shell app-workspace-body">
        <AppPageHeader kicker="Pipeline" title={title} lead={detail} />
        <div className="upload-panel pipeline-empty-panel">
          <div className="pipeline-empty-body">
            <span className="pipeline-empty-icon" aria-hidden="true">
              1→2
            </span>
            <p className="upload-hint">
              This step is part of the pipeline after you create an opportunity on the upload page.
            </p>
            <p>Start there, then use <strong>Review framework</strong> once an opportunity is active.</p>

            <Link href="/upload" className="btn btn-primary">
              Go to upload
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
