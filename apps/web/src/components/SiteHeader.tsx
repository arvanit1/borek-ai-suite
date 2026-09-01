"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BrandLogo } from "@/components/BrandLogo";
import { SignOutButton } from "@/components/SignOutButton";
import { useAuth } from "@/components/AuthProvider";
import { loadActiveOpportunity, pipelineHref, saveActiveOpportunityId } from "@/lib/pipelineContext";

interface SiteHeaderProps {
  signedInEmail?: string | null;
  opportunityId?: string | null;
}

export function SiteHeader({ signedInEmail, opportunityId }: SiteHeaderProps) {
  const { session } = useAuth();
  const email = signedInEmail ?? session?.user.email ?? null;
  const [storedOpportunityId, setStoredOpportunityId] = useState<string | null>(null);

  useEffect(() => {
    if (opportunityId) {
      saveActiveOpportunityId(opportunityId);
      setStoredOpportunityId(opportunityId);
      return;
    }
    setStoredOpportunityId(loadActiveOpportunity()?.id ?? null);
  }, [opportunityId]);

  const resolvedOpportunityId = opportunityId ?? storedOpportunityId;

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <BrandLogo showProductName href={pipelineHref("/upload", resolvedOpportunityId)} />
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
