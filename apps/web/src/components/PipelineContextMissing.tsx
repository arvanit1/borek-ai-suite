import Link from "next/link";

import { SiteHeader } from "@/components/SiteHeader";

interface PipelineContextMissingProps {
  title: string;
  detail: string;
}

/** Shown when a pipeline step is opened without ?opportunityId= (expected after upload). */
export function PipelineContextMissing({ title, detail }: PipelineContextMissingProps) {
  return (
    <div className="upload-page">
      <SiteHeader />
      <div className="app-shell pipeline-empty-page">
        <div className="upload-panel pipeline-empty-panel">
          <header className="upload-panel-header">
            <div>
              <h1>{title}</h1>
              <p>{detail}</p>
            </div>
          </header>
          <div className="pipeline-empty-body">
            <span className="pipeline-empty-icon" aria-hidden="true">
              1→2
            </span>
            <p className="upload-hint">
              This step is part of the pipeline after you create an opportunity on the upload page.
              Start there, then use <strong>Review framework</strong> once an opportunity is active.
            </p>
            <Link href="/upload" className="btn btn-primary">
              Go to upload
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
