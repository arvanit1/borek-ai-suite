import { RequireAuth } from "@/components/RequireAuth";
import { TranscriptUploadPanel } from "@/components/TranscriptUploadPanel";

interface UploadPageProps {
  searchParams: Promise<{ opportunityId?: string; new?: string }>;
}

export default async function UploadPage({ searchParams }: UploadPageProps) {
  const params = await searchParams;
  const opportunityId = params.opportunityId?.trim() || null;
  const startFresh = params.new === "1";

  return (
    <RequireAuth>
      <TranscriptUploadPanel initialOpportunityId={opportunityId} startFresh={startFresh} />
    </RequireAuth>
  );
}
