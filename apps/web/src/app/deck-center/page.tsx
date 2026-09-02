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
          title="Your presentation"
          detail="Preview slides and download the generated PowerPoint for an opportunity."
        />
      ) : (
        <DeckCenterPanel opportunityId={opportunityId} />
      )}
    </RequireAuth>
  );
}
