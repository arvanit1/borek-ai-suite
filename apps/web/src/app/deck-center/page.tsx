import { DeckCenterPanel } from "@/components/DeckCenterPanel";

interface DeckCenterPageProps {
  searchParams: Promise<{ opportunityId?: string }>;
}

export default async function DeckCenterPage({ searchParams }: DeckCenterPageProps) {
  const params = await searchParams;
  const opportunityId = params.opportunityId?.trim() ?? "";

  if (!opportunityId) {
    return (
      <div className="app-shell">
        <h1>Deck center</h1>
        <p className="upload-hint">
          Open this page with an opportunity id, for example{" "}
          <code>/deck-center?opportunityId=&lt;uuid&gt;</code>.
        </p>
      </div>
    );
  }

  return <DeckCenterPanel opportunityId={opportunityId} />;
}
