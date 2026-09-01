import { RecentPresentationsPanel } from "@/components/RecentPresentationsPanel";
import { RequireAuth } from "@/components/RequireAuth";

export default function HomePage() {
  return (
    <RequireAuth>
      <RecentPresentationsPanel />
    </RequireAuth>
  );
}
