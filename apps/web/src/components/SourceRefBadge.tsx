import type { ConversationRef } from "@/lib/frameworkTypes";
import { formatSourceRefDetail, formatSourceRefLabel } from "@/lib/frameworkEdit";

interface SourceRefBadgeProps {
  refItem: ConversationRef;
}

export function SourceRefBadge({ refItem }: SourceRefBadgeProps) {
  const label = formatSourceRefLabel(refItem);
  const detail = formatSourceRefDetail(refItem);
  return (
    <details className="source-ref-badge">
      <summary>{label}</summary>
      <p className="source-ref-detail">
        <span>{detail}</span>
      </p>
    </details>
  );
}
