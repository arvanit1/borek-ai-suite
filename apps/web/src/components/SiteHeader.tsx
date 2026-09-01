"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { BrandLogo } from "@/components/BrandLogo";
import { SignOutButton } from "@/components/SignOutButton";
import { useAuth } from "@/components/AuthProvider";

interface SiteHeaderProps {
  signedInEmail?: string | null;
  opportunityId?: string | null;
}

const PIPELINE_LINKS = [
  { id: "upload", href: "/upload", label: "Upload" },
  { id: "framework", href: "/framework-review", label: "Framework" },
  { id: "plan", href: "/plan-preview", label: "Plan" },
  { id: "deck", href: "/deck-center", label: "Deck" },
] as const;

function pipelineHref(path: string, opportunityId?: string | null): string {
  if (path === "/upload" || !opportunityId) {
    return path;
  }
  return `${path}?opportunityId=${encodeURIComponent(opportunityId)}`;
}

function isActivePath(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SiteHeader({ signedInEmail, opportunityId }: SiteHeaderProps) {
  const pathname = usePathname();
  const { session } = useAuth();
  const email = signedInEmail ?? session?.user.email ?? null;

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <BrandLogo showProductName />
        <nav className="site-pipeline" aria-label="Pipeline">
          {PIPELINE_LINKS.map((item) => {
            const active = isActivePath(pathname, item.href);
            return (
              <Link
                key={item.id}
                href={pipelineHref(item.href, opportunityId)}
                className={`site-pipeline-link${active ? " site-pipeline-link-active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="site-nav">
          {email ? (
            <>
              <span className="site-user" title={email}>
                {email}
              </span>
              <SignOutButton />
            </>
          ) : (
            <>
              <Link href="/login">Sign in</Link>
              <Link href="/register" className="site-nav-cta">
                Register
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
