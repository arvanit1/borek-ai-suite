import Link from "next/link";

import { BrandLogo } from "@/components/BrandLogo";
import { SignOutButton } from "@/components/SignOutButton";

interface SiteHeaderProps {
  signedInEmail?: string | null;
}

export function SiteHeader({ signedInEmail }: SiteHeaderProps) {
  return (
    <header className="site-header">
      <BrandLogo showProductName />
      <nav className="site-nav" aria-label="Main">
        <Link href="/upload">Upload</Link>
        {signedInEmail ? (
          <>
            <span className="site-user">{signedInEmail}</span>
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
    </header>
  );
}
