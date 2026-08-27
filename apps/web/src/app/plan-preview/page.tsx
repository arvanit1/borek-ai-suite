import { PipelineContextMissing } from "@/components/PipelineContextMissing";
import { PlanPreviewPanel } from "@/components/PlanPreviewPanel";
import { RequireAuth } from "@/components/RequireAuth";

interface PlanPreviewPageProps {
  searchParams: Promise<{ opportunityId?: string }>;
}

export default async function PlanPreviewPage({ searchParams }: PlanPreviewPageProps) {
  const params = await searchParams;
  const opportunityId = params.opportunityId?.trim() ?? "";

  return (
    <RequireAuth>
      {!opportunityId ? (
        <PipelineContextMissing
          title="Presentation plan preview"
          detail="Inspect slide order, purpose, and layout before generating the deck."
        />
      ) : (
        <PlanPreviewPanel opportunityId={opportunityId} />
      )}
    </RequireAuth>
  );
}
