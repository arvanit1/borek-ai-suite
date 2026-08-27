import { RequireAuth } from "@/components/RequireAuth";
import { TranscriptUploadPanel } from "@/components/TranscriptUploadPanel";

export default function UploadPage() {
  return (
    <RequireAuth>
      <TranscriptUploadPanel />
    </RequireAuth>
  );
}
