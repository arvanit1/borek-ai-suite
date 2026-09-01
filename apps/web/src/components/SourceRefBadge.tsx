import type { ConversationRef } from "@/lib/frameworkTypes";
import { formatSourceRefDetail, formatSourceRefLabel } from "@/lib/frameworkEdit";

interface SourceRefBadgeProps {
  refItem: ConversationRef;
}

export function SourceRefBadge({ refItem }: SourceRefBadgeProps) {
  const label = formatSourceRefLabel(refItem);
  return (
    <span className="source-ref-badge" title={formatSourceRefDetail(refItem)}>
      {label}
    </span>
  );
}
