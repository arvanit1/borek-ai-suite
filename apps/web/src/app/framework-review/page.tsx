import { FrameworkReviewPanel } from "@/components/FrameworkReviewPanel";

interface FrameworkReviewPageProps {
  searchParams: Promise<{ opportunityId?: string }>;
}

export default async function FrameworkReviewPage({ searchParams }: FrameworkReviewPageProps) {
  const params = await searchParams;
  const opportunityId = params.opportunityId?.trim() ?? "";

  if (!opportunityId) {
    return (
      <div className="app-shell">
        <h1>Framework review</h1>
        <p className="upload-hint">
          Open this page with an opportunity id, for example{" "}
          <code>/framework-review?opportunityId=&lt;uuid&gt;</code>.
        </p>
      </div>
    );
  }

  return <FrameworkReviewPanel opportunityId={opportunityId} />;
}
