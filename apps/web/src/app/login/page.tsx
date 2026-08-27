import { AuthCard } from "@/components/AuthCard";
import { AuthShell } from "@/components/AuthShell";

export default function LoginPage() {
  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to create opportunities and upload client transcripts."
    >
      <AuthCard mode="sign-in" />
    </AuthShell>
  );
}
