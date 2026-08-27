import { BrandLogo } from "@/components/BrandLogo";

interface AuthShellProps {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}

export function AuthShell({ title, subtitle, children }: AuthShellProps) {
  return (
    <div className="auth-page">
      <div className="auth-layout">
        <aside className="auth-brand">
          <BrandLogo href="/login" />
          <p className="auth-product-name">Pitch Factory</p>
          <p className="auth-tagline">
            Framework and presentation generation for sales engineering teams.
          </p>
        </aside>

        <main className="auth-main">
          <div className="auth-main-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
