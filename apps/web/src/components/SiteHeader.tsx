import Link from "next/link";

interface SiteHeaderProps {
  signedInEmail?: string | null;
}

export function SiteHeader({ signedInEmail }: SiteHeaderProps) {
  return (
    <header className="site-header">
      <Link href="/upload" className="site-logo">
        Borek AI Suite
      </Link>
      <nav className="site-nav">
        <Link href="/upload">Upload</Link>
        <Link href="/framework-review">Framework</Link>
        {signedInEmail ? (
          <span className="site-user">{signedInEmail}</span>
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
