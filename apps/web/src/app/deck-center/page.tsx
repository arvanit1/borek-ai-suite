import { DeckCenterPanel } from "@/components/DeckCenterPanel";
import { PipelineContextMissing } from "@/components/PipelineContextMissing";
import { RequireAuth } from "@/components/RequireAuth";

interface DeckCenterPageProps {
  searchParams: Promise<{ opportunityId?: string }>;
}

export default async function DeckCenterPage({ searchParams }: DeckCenterPageProps) {
  const params = await searchParams;
  const opportunityId = params.opportunityId?.trim() ?? "";

  return (
    <RequireAuth>
      {!opportunityId ? (
        <PipelineContextMissing
          title="Deck center"
          detail="Preview slide PNGs and download the generated presentation for an opportunity."
        />
      ) : (
        <DeckCenterPanel opportunityId={opportunityId} />
      )}
    </RequireAuth>
  );
}
