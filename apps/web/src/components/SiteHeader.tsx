"use client";

import Link from "next/link";

import { BrandLogo } from "@/components/BrandLogo";
import { SignOutButton } from "@/components/SignOutButton";
import { useAuth } from "@/components/AuthProvider";

interface SiteHeaderProps {
  signedInEmail?: string | null;
  opportunityId?: string | null;
}

export function SiteHeader({ signedInEmail }: SiteHeaderProps) {
  const { session } = useAuth();
  const email = signedInEmail ?? session?.user.email ?? null;

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <BrandLogo showProductName href="/" />
        <nav className="site-nav" aria-label="Main navigation">
          {email ? (
            <>
              <Link href="/" className="site-nav-recent">Recent</Link>
              <Link href="/upload?new=1" className="site-nav-new">
                <span className="site-nav-new-full">New presentation</span>
                <span className="site-nav-new-short">New</span>
              </Link>
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
        </nav>
      </div>
    </header>
  );
}
