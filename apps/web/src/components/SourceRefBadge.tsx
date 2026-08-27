import type { ConversationRef } from "@/lib/frameworkTypes";
import { formatSourceRefLabel } from "@/lib/frameworkEdit";

interface SourceRefBadgeProps {
  refItem: ConversationRef;
}

export function SourceRefBadge({ refItem }: SourceRefBadgeProps) {
  return (
    <span className="source-ref-badge" title={formatSourceRefLabel(refItem)}>
      <span className="source-ref-badge-label">Source</span>
      <span className="source-ref-badge-value">{formatSourceRefLabel(refItem)}</span>
    </span>
  );
}
