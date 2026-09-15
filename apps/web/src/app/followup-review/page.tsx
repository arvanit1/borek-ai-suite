import { FollowupReviewPanel } from "@/components/FollowupReviewPanel";
import { PipelineContextMissing } from "@/components/PipelineContextMissing";
import { RequireAuth } from "@/components/RequireAuth";

export default async function FollowupReviewPage({
  searchParams,
}: {
  searchParams: Promise<{ opportunityId?: string }>;
}) {
  const opportunityId = (await searchParams).opportunityId?.trim() ?? "";
  return (
    <RequireAuth>
      {opportunityId ? (
        <FollowupReviewPanel opportunityId={opportunityId} />
      ) : (
        <PipelineContextMissing
          title="Follow-up review"
          detail="Open this review from an opportunity after follow-up data is available."
        />
      )}
    </RequireAuth>
  );
}
