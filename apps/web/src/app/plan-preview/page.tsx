import { PlanPreviewPanel } from "@/components/PlanPreviewPanel";

interface PlanPreviewPageProps {
  searchParams: Promise<{ opportunityId?: string }>;
}

export default async function PlanPreviewPage({ searchParams }: PlanPreviewPageProps) {
  const params = await searchParams;
  const opportunityId = params.opportunityId?.trim() ?? "";

  if (!opportunityId) {
    return (
      <div className="app-shell">
        <h1>Presentation plan preview</h1>
        <p className="upload-hint">
          Open this page with an opportunity id, for example{" "}
          <code>/plan-preview?opportunityId=&lt;uuid&gt;</code>.
        </p>
      </div>
    );
  }

  return <PlanPreviewPanel opportunityId={opportunityId} />;
}
