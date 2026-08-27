import { AuthCard } from "@/components/AuthCard";
import { AuthShell } from "@/components/AuthShell";

export default function RegisterPage() {
  return (
    <AuthShell
      title="Create your account"
      subtitle="Register to access the transcript upload and presentation pipeline."
    >
      <AuthCard mode="sign-up" />
    </AuthShell>
  );
}
