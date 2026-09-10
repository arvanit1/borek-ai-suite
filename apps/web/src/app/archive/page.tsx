import { ArchiveHistoryPanel } from "@/components/ArchiveHistoryPanel";
import { RequireAuth } from "@/components/RequireAuth";

export default function ArchivePage() {
  return (
    <RequireAuth>
      <ArchiveHistoryPanel />
    </RequireAuth>
  );
}
