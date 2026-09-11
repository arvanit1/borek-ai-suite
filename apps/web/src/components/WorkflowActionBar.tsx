import Link from "next/link";
import React, { type ReactNode } from "react";

interface WorkflowActionBarProps {
  backHref: string;
  backLabel: string;
  contextLabel: string;
  context: ReactNode;
  children: ReactNode;
}

export function WorkflowActionBar({
  backHref,
  backLabel,
  contextLabel,
  context,
  children,
}: WorkflowActionBarProps) {
  return (
    <section className="workflow-action-bar" aria-label="Workflow actions">
      <Link href={backHref} className="btn btn-secondary workflow-action-back">
        {backLabel}
      </Link>
      <div className="workflow-action-context">
        <span>{contextLabel}</span>
        <div>{context}</div>
      </div>
      <div className="workflow-action-controls">{children}</div>
    </section>
  );
}
