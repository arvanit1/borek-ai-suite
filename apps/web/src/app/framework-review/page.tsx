import { FrameworkReviewPanel } from "@/components/FrameworkReviewPanel";
import { PipelineContextMissing } from "@/components/PipelineContextMissing";
import { RequireAuth } from "@/components/RequireAuth";

interface FrameworkReviewPageProps {
  searchParams: Promise<{ opportunityId?: string }>;
}

export default async function FrameworkReviewPage({ searchParams }: FrameworkReviewPageProps) {
  const params = await searchParams;
  const opportunityId = params.opportunityId?.trim() ?? "";

  return (
    <RequireAuth>
      {!opportunityId ? (
        <PipelineContextMissing
          title="Framework review"
          detail="Review and edit the 14-chapter framework for a specific opportunity."
        />
      ) : (
        <FrameworkReviewPanel opportunityId={opportunityId} />
      )}
    </RequireAuth>
  );
}
