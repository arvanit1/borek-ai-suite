import { RequireAuth } from "@/components/RequireAuth";
import { TranscriptUploadPanel } from "@/components/TranscriptUploadPanel";

interface UploadPageProps {
  searchParams: Promise<{ opportunityId?: string }>;
}

export default async function UploadPage({ searchParams }: UploadPageProps) {
  const params = await searchParams;
  const opportunityId = params.opportunityId?.trim() || null;

  return (
    <RequireAuth>
      <TranscriptUploadPanel initialOpportunityId={opportunityId} />
    </RequireAuth>
  );
}
